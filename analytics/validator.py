import pandas as pd
import re


class FreshserviceFieldValidator:
    """
    Validates mandatory Freshservice ticket fields marked with red asterisks (*).
    Audits fields: Priority, Status, Urgency, Group, Company, Alarm Source, Affected CI, Issue Bucket.
    Uses normalized, fuzzy key-matching to safely extract column values.
    """

    MANDATORY_FIELD_MAP = {
        "Priority": ["priority"],
        "Status": ["status"],
        "Urgency": ["urgency", "priority"],
        "Group": ["group", "ticket_group", "assigned_group", "group_name"],
        "Company": ["company", "company_name", "account_name"],
        "Alarm Source": ["alarm_source", "alarmsource", "alarm", "source"],
        "Affected CI": ["affected_ci", "affectedci", "ci", "asset", "affected_item"],
        "Issue Bucket": ["issue_bucket", "issuebucket", "bucket", "ticket_type", "type", "category"]
    }

    INVALID_TOKENS = {"", "nan", "none", "--", "null", "undefined", "n/a", "unknown", "-"}

    @staticmethod
    def _normalize_key(key: str) -> str:
        """Strips underscores, spaces, and hyphens and lowercases string."""
        return re.sub(r'[\s_\-]+', '', str(key)).lower()

    @classmethod
    def _get_field_value(cls, ticket: dict, target_aliases: list) -> str:
        """
        Safely searches the ticket dictionary using fuzzy key-matching
        across all target aliases.
        """
        # Build normalized dictionary lookup map from ticket keys
        normalized_ticket = {cls._normalize_key(k): v for k, v in ticket.items() if v is not None}

        for alias in target_aliases:
            norm_alias = cls._normalize_key(alias)
            if norm_alias in normalized_ticket:
                raw_val = normalized_ticket[norm_alias]
                cleaned_val = str(raw_val).strip()
                if cleaned_val.lower() not in cls.INVALID_TOKENS:
                    return cleaned_val
        return ""

    @classmethod
    def validate_ticket(cls, ticket: dict) -> dict:
        missing_mandatory = []

        # Check each mandatory field using fuzzy matching
        for field_label, aliases in cls.MANDATORY_FIELD_MAP.items():
            val = cls._get_field_value(ticket, aliases)
            if not val or val.lower() in cls.INVALID_TOKENS:
                missing_mandatory.append(field_label)

        total_mandatory = len(cls.MANDATORY_FIELD_MAP)
        passed_count = total_mandatory - len(missing_mandatory)
        compliance_score = round((passed_count / total_mandatory) * 100, 1)

        return {
            "is_compliant": len(missing_mandatory) == 0,
            "missing_fields": missing_mandatory,
            "compliance_score": compliance_score
        }

    @classmethod
    def batch_audit_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Audits an entire DataFrame and appends validation metrics."""
        if df.empty:
            return df.copy()

        results = []
        for _, row in df.iterrows():
            audit = cls.validate_ticket(row.to_dict())
            results.append({
                "field_compliant": 1 if audit["is_compliant"] else 0,
                "missing_fields_count": len(audit["missing_fields"]),
                "missing_fields_list": ", ".join(audit["missing_fields"]) if audit["missing_fields"] else "None",
                "form_quality_score": audit["compliance_score"]
            })

        audit_df = pd.DataFrame(results, index=df.index)
        return pd.concat([df, audit_df], axis=1)

    @classmethod
    def generate_agent_scorecard(cls, audited_df: pd.DataFrame) -> pd.DataFrame:
        """Aggregates form compliance metrics per agent."""
        if audited_df.empty or "agent" not in audited_df.columns:
            return pd.DataFrame()

        summary = (
            audited_df.groupby("agent")
            .agg(
                Total_Tickets=("ticket_id", "count"),
                Compliant_Forms=("field_compliant", "sum"),
                Missing_Field_Tickets=("missing_fields_count", lambda x: (x > 0).sum()),
                Avg_Form_Quality_Score=("form_quality_score", "mean")
            )
            .reset_index()
        )

        summary["Compliance_Rate"] = (
            (summary["Compliant_Forms"] / summary["Total_Tickets"]) * 100
        ).round(1)
        summary["Avg_Form_Quality_Score"] = summary["Avg_Form_Quality_Score"].round(1)

        return summary[
            [
                "agent",
                "Total_Tickets",
                "Compliant_Forms",
                "Missing_Field_Tickets",
                "Compliance_Rate",
                "Avg_Form_Quality_Score"
            ]
        ].sort_values(by="Avg_Form_Quality_Score", ascending=False)
