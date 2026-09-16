export type ExecutionEventStatus = "allowed" | "review" | "blocked" | "violation" | string;

export type ExecutionEvent = {
  seq: number;
  type: string;
  title: string;
  detail: string;
  status: ExecutionEventStatus;
};

type LegacyEvidence = Record<string, any> & { type?: string };

export function toExecutionEvents(source: { events?: ExecutionEvent[]; evidence?: LegacyEvidence[] } | LegacyEvidence[]): ExecutionEvent[] {
  if (!Array.isArray(source) && Array.isArray(source.events)) return source.events;
  const evidence = Array.isArray(source) ? source : source.evidence || [];
  return evidence.map((item, index) => {
    const type = item.type || "observation";
    const action = type === "action";
    const title = action ? item.name || "Tool action" : ({ confirmation: "User confirmation", state_change: "State change", task_outcome: "Task outcome", nl_assertion: "Goal evaluation", db_check: "Database state check" } as Record<string, string>)[type] || type;
    const orderId = item.arguments?.order_id ? ` · ${item.arguments.order_id}` : "";
    const detail = action
      ? `${item.tool_type === "write" ? "state-changing write" : "read-only"}${orderId} · ${item.matched === false ? "expected result mismatch" : "matched"}`
      : type === "confirmation" ? `confirmation ${item.observed ? "observed before action" : "required but not observed"}`
        : type === "state_change" ? `state change ${item.observed ? "observed" : "not observed"}`
          : type === "task_outcome" ? `task ${item.completed ? "completed" : "not completed"}`
            : type === "db_check" ? `database match ${item.db_match ? "confirmed" : "not confirmed"}`
              : item.justification || `${type} recorded`;
    const status = action ? (item.matched === false ? "violation" : "allowed")
      : type === "confirmation" ? (item.observed ? "allowed" : "review")
        : type === "state_change" ? (item.observed ? "allowed" : "blocked")
          : type === "task_outcome" ? (item.completed ? "allowed" : "blocked")
            : (item.met === false || item.db_match === false ? "violation" : "allowed");
    return { seq: item.seq ?? index + 1, type, title, detail, status };
  });
}

declare global { interface Window { ReinEvents?: { toExecutionEvents: typeof toExecutionEvents } } }
if (typeof window !== "undefined") window.ReinEvents = { toExecutionEvents };
