import { Hono } from "hono";
import type { Env } from "../../env";
import { failure } from "../envelope";
import { InvalidPageParam } from "../pagination";
import { corpus } from "./corpus";
import { integrations } from "./integrations";
import { push } from "./push";
import { reports } from "./reports";
import { results } from "./results";
import { specs } from "./specs";
import { tasks } from "./tasks";

export const apiV1 = new Hono<{ Bindings: Env }>()
  .onError((error, c) => {
    if (error instanceof InvalidPageParam) return failure(c, error.message, "invalid_query_param");
    throw error;
  })
  .route("/specs", specs)
  .route("/results", results)
  .route("/tasks", tasks)
  .route("/integrations", integrations)
  .route("/corpus", corpus)
  .route("/reports", reports)
  .route("/", push);
