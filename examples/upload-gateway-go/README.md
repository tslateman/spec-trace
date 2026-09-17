# Upload Gateway (Go)

A Go example that links `go test` subtests to requirements through the bracketed
tag SpecTrace reads from any JUnit report.

The gateway admits the media types the pipeline can process (`GW-UPL-001`), caps
a single upload at 100 MB (`GW-UPL-002`), and holds each tenant to its request
budget (`GW-RTL-001`).

## Layout

```
upload-gateway-go/
├── spectrace-map.yaml           # project: upload-gateway
├── specs/gateway/
│   ├── GW-001.md                # Root requirement
│   ├── GW-UPL-001.md            # Supported media types
│   ├── GW-UPL-002.md            # Upload size cap
│   └── GW-RTL-001.md            # Per-tenant rate limit
├── gateway.go
├── gateway_test.go
└── ci/github-actions.yml
```

## Linking a test

Name the subtest after the requirement it verifies:

```go
func TestAccepts(t *testing.T) {
	t.Run("[GW-UPL-001] admits the media types the pipeline processes", func(t *testing.T) {
		...
	})
}
```

Go replaces the spaces with underscores, so the report carries
`TestAccepts/[GW-UPL-001]_admits_the_media_types_the_pipeline_processes`. The
tag survives, and that is all SpecTrace reads.

## Running it

`go test` writes no JUnit, so `gotestsum` wraps it:

```bash
go install gotest.tools/gotestsum@latest
gotestsum --junitfile junit.xml --format testname ./...
```

```
PASS TestAccepts/[GW-UPL-001]_admits_the_media_types_the_pipeline_processes (0.00s)
PASS TestWithinSizeCap/[GW-UPL-002]_admits_an_upload_of_exactly_the_cap (0.00s)
PASS TestRateLimiter/[GW-RTL-001]_spends_the_budget_and_then_refuses (0.00s)
...
DONE 10 tests in 0.310s
```

## Pushing

One file carries both the links and the results:

```bash
spectrace push --specs specs --links junit.xml --replace
spectrace results push junit.xml
```

`ci/github-actions.yml` runs the same three commands on every push.
