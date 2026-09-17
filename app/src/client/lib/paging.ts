import { useSearchParams } from "react-router-dom";

export function usePaging() {
  const [params, setParams] = useSearchParams();

  function goToPage(target: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(target));
    setParams(next);
  }

  function setPageSize(size: number) {
    const next = new URLSearchParams(params);
    next.set("per_page", String(size));
    next.delete("page");
    setParams(next);
  }

  return { params, setParams, query: params.toString(), goToPage, setPageSize };
}
