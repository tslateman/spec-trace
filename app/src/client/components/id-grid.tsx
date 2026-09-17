import { Link } from "react-router-dom";
import { Empty } from "@/client/components/panel";

export function IdGrid({ ids, link }: { ids: string[]; link?: boolean }) {
  if (ids.length === 0) return <Empty>None</Empty>;
  return (
    <ul className="flex flex-wrap gap-2">
      {ids.map((id) => (
        <li key={id} className="rounded bg-muted px-2 py-1 font-mono text-xs">
          {link ? <Link to={`/specs/${encodeURIComponent(id)}`}>{id}</Link> : id}
        </li>
      ))}
    </ul>
  );
}
