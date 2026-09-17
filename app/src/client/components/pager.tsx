import { Button } from "@/client/components/ui/button";

export const PAGE_SIZES = [25, 50, 100];

export function Pager({
  shown,
  total,
  noun,
  position,
  hasPrev,
  hasNext,
  onPrev,
  onNext,
  pageSize,
  onPageSize,
}: {
  shown: number;
  total: number;
  noun: string;
  position?: string;
  hasPrev: boolean;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  pageSize?: number;
  onPageSize?: (size: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
      <span>
        {shown} of {total} {noun}
        {position ? ` · ${position}` : ""}
      </span>
      <div className="flex items-center gap-2">
        {pageSize && onPageSize && (
          <select
            value={pageSize}
            onChange={(event) => onPageSize(Number(event.target.value))}
            className="h-9 rounded-md border border-border bg-background px-2 text-sm"
            aria-label="Rows per page"
          >
            {(PAGE_SIZES.includes(pageSize) ? PAGE_SIZES : [pageSize, ...PAGE_SIZES]).map((size) => (
              <option key={size} value={size}>
                {size} per page
              </option>
            ))}
          </select>
        )}
        <Button variant="ghost" size="sm" disabled={!hasPrev} onClick={onPrev}>
          Previous
        </Button>
        <Button variant="ghost" size="sm" disabled={!hasNext} onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  );
}
