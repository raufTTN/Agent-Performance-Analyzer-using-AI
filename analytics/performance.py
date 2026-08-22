import pandas as pd


class ComprehensivePerformanceEngine:

    # Existing performance = 60%
    # Freshservice field completion = 40%

    @staticmethod
    def _filled_score(series):
        """
        Any meaningful non-empty value = 100%
        Blank/null = 0%
        """
        if series is None or len(series) == 0:
            return 0.0

        values = series.fillna("").astype(str).str.strip()

        valid = (
            values.ne("")
            & ~values.str.lower().isin(
                ["nan", "none", "null", "n/a", "na", "-"]
            )
        )

        return round(valid.mean() * 100, 2)

    @staticmethod
    def _grade(score):
        if score >= 90:
            return "A+ - Excellent"
        elif score >= 80:
            return "A - Very Good"
        elif score >= 70:
            return "B - Good"
        elif score >= 60:
            return "C - Needs Improvement"
        else:
            return "D - Poor"

    @classmethod
    def calculate_agent_metrics(cls, df):

        if df is None or df.empty:
            return pd.DataFrame()

        if "agent" not in df.columns:
            return pd.DataFrame()

        result = []

        # ---------------------------------------------------------
        # Team median ticket volume
        # ---------------------------------------------------------

        ticket_counts = df.groupby("agent").size()

        median_volume = ticket_counts.median()

        if median_volume <= 0:
            median_volume = 1

        for agent, agent_df in df.groupby("agent"):

            if not str(agent).strip():
                continue

            total_tickets = len(agent_df)

            # =====================================================
            # EXISTING PERFORMANCE
            # =====================================================

            # 1. Ticket Volume - 10%
            ticket_volume_score = min(
                100,
                round(
                    (total_tickets / median_volume) * 100,
                    2,
                ),
            )

            # 2. SLA Compliance - 15%
            if "sla_breached" in agent_df.columns:

                sla_values = pd.to_numeric(
                    agent_df["sla_breached"],
                    errors="coerce",
                ).fillna(1)

                sla_score = round(
                    (sla_values == 0).mean() * 100,
                    2,
                )

            else:
                sla_score = 0

            # 3. Resolution Time - 10%
            if "resolution_hours" in agent_df.columns:

                resolution = pd.to_numeric(
                    agent_df["resolution_hours"],
                    errors="coerce",
                ).dropna()

                if not resolution.empty:

                    def resolution_score(hours):

                        if hours <= 4:
                            return 100
                        elif hours <= 8:
                            return 90
                        elif hours <= 16:
                            return 75
                        elif hours <= 24:
                            return 60
                        else:
                            return max(
                                20,
                                60 - ((hours - 24) * 1.5),
                            )

                    resolution_time_score = round(
                        resolution.apply(
                            resolution_score
                        ).mean(),
                        2,
                    )

                else:
                    resolution_time_score = 0

            else:
                resolution_time_score = 0

            # 4. Effort - 10%
            if "effort_mins" in agent_df.columns:

                effort = pd.to_numeric(
                    agent_df["effort_mins"],
                    errors="coerce",
                )

                valid_effort = effort.notna() & (effort > 0)

                effort_score = round(
                    valid_effort.mean() * 100,
                    2,
                )

            else:
                effort_score = 0

            # 5. Priority Handling - 10%
            if "priority" in agent_df.columns:

                priority = (
                    agent_df["priority"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

                priority_score = round(
                    priority.ne("").mean() * 100,
                    2,
                )

            else:
                priority_score = 0

            # 6. SR / Incident Classification - 5%
            if "ticket_type" in agent_df.columns:

                ticket_type = (
                    agent_df["ticket_type"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )

                classification_score = round(
                    ticket_type.ne("").mean() * 100,
                    2,
                )

            else:
                classification_score = 0

            # =====================================================
            # NEW FRESHSERVICE FIELD PERFORMANCE
            # =====================================================

            # Every correctly populated field contributes 5%.
            #
            # Example:
            # 100% tickets have Affected CI filled
            # = 5/5 points
            #
            # 80% tickets have Affected CI filled
            # = 4/5 points

            quality_fields = {
                "Affected CI": "affected_ci",
                "Other Affected CI": "other_affected_ci",
                "Issue Bucket": "issue_bucket",
                "Resolution Applied": "resolution_applied",
                "Resolution Note": "resolution_note",
                "Escalation": "escalation",
                "Category": "category",
                "Sub-category": "sub_category",
            }

            quality_scores = {}

            for display_name, column_name in quality_fields.items():

                if column_name in agent_df.columns:

                    quality_scores[display_name] = (
                        cls._filled_score(
                            agent_df[column_name]
                        )
                    )

                else:
                    quality_scores[display_name] = 0

            # =====================================================
            # FINAL WEIGHTED SCORE
            # =====================================================

            existing_score = (
                ticket_volume_score * 0.10
                + sla_score * 0.15
                + resolution_time_score * 0.10
                + effort_score * 0.10
                + priority_score * 0.10
                + classification_score * 0.05
            )

            quality_score = (
                quality_scores["Affected CI"] * 0.05
                + quality_scores["Other Affected CI"] * 0.05
                + quality_scores["Issue Bucket"] * 0.05
                + quality_scores["Resolution Applied"] * 0.05
                + quality_scores["Resolution Note"] * 0.05
                + quality_scores["Escalation"] * 0.05
                + quality_scores["Category"] * 0.05
                + quality_scores["Sub-category"] * 0.05
            )

            overall_score = round(
                existing_score + quality_score,
                2,
            )

            result.append(
                {
                    "Agent": agent,
                    "Tickets Handled": total_tickets,

                    # Existing
                    "Ticket Volume": ticket_volume_score,
                    "SLA Compliance": sla_score,
                    "Resolution Time": resolution_time_score,
                    "Effort": effort_score,
                    "Priority Handling": priority_score,
                    "SR/Incident Classification": classification_score,

                    # New Freshservice fields
                    "Affected CI": quality_scores["Affected CI"],
                    "Other Affected CI": quality_scores[
                        "Other Affected CI"
                    ],
                    "Issue Bucket": quality_scores["Issue Bucket"],
                    "Resolution Applied": quality_scores[
                        "Resolution Applied"
                    ],
                    "Resolution Note": quality_scores[
                        "Resolution Note"
                    ],
                    "Escalation": quality_scores["Escalation"],
                    "Category": quality_scores["Category"],
                    "Sub-category": quality_scores[
                        "Sub-category"
                    ],

                    # Final
                    "Performance Score": overall_score,
                    "Performance Grade": cls._grade(
                        overall_score
                    ),
                }
            )

        performance_df = pd.DataFrame(result)

        if performance_df.empty:
            return performance_df

        # Rank agents
        performance_df = performance_df.sort_values(
            "Performance Score",
            ascending=False,
        ).reset_index(drop=True)

        performance_df.insert(
            0,
            "Rank",
            range(1, len(performance_df) + 1),
        )

        return performance_df