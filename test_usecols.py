import pandas as pd
import re
from io import StringIO

cols = ["Subject", "Type", "Status", "Urgency", "Impact", "Priority", "Group", "Agent", "Company", "Description", "Category", "Sub-Category", "Item", "Source", "Resolution Note", "Experience Score", "Association type", "Requester Location", "Requester VIP", "Ticket Id", "Requester Name", "Requester Email", "Created Time", "Due by Time", "Resolved Time", "Closed Time", "Last Updated Time", "Initial Response Time", "Time Tracked", "First Response Time (in Hrs)", "Resolution Time (in Hrs)", "Agent interactions", "Customer interactions", "Resolution Status", "First Response Status", "Tags", "Survey Result", "Approval Status", "Subscriber Id / Sub-Company", "Device Details", "Resolved By Level", "Monitoring Status", "Major incident type", "Business impact", "Impacted locations", "No. of customers impacted", "Effort Required to Resolve (in mins)", "Alarm Source", "Others", "Affected CI", "Other Affected CI", "Parent Ticket ID", "Issue Bucket", "Resolution Applied", "Sub-Resolution Code", "Others", "Impact Category", "Escalated", "Escalation", "Partner ID", "Hosted On", "Escalated Date", "RCA Submission Date", "Resolved via KB?", "Article Number", "Merged", "Customer updated the status"]

csv_header = ",".join(cols) + "\n" + ",".join(["1"]*len(cols))

required_normalized = {
    "createdtime", "resolvedtime", "subject", "description", "priority", "agent",
    "resolutionapplied", "resolutionnote", "status", "effortrequiredtoresolve(inmins)",
    "resolutionhours", "ticketid", "id", "group", "ticketgroup", "assignedgroup",
    "alarmsource", "source", "affectedci", "ci", "asset", "issuebucket", "bucket",
    "tickettype", "type", "urgency", "company", "accountname", "category"
}

def is_required_col(col_name: str) -> bool:
    norm_col = re.sub(r'[\s_\-]+', '', str(col_name)).lower()
    return norm_col in required_normalized

try:
    df = pd.read_csv(StringIO(csv_header), usecols=is_required_col)
    print("SUCCESS")
    print(df.columns.tolist())
except Exception as e:
    print("ERROR:", e)
