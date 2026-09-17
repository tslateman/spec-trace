package gateway

import "testing"

// A subtest name carries the requirement it verifies in brackets. Go replaces
// the spaces with underscores; SpecTrace reads the tag either way.

func TestAccepts(t *testing.T) {
	t.Run("[GW-UPL-001] admits the media types the pipeline processes", func(t *testing.T) {
		for _, mediaType := range []string{"application/pdf", "image/png", "image/jpeg"} {
			if !Accepts(mediaType) {
				t.Errorf("Accepts(%q) = false, want true", mediaType)
			}
		}
	})

	t.Run("[GW-UPL-001] refuses an executable and an empty media type", func(t *testing.T) {
		for _, mediaType := range []string{"application/x-msdownload", ""} {
			if Accepts(mediaType) {
				t.Errorf("Accepts(%q) = true, want false", mediaType)
			}
		}
	})
}

func TestWithinSizeCap(t *testing.T) {
	t.Run("[GW-UPL-002] admits an upload of exactly the cap", func(t *testing.T) {
		if !WithinSizeCap(MaxUploadBytes) {
			t.Error("an upload of exactly the cap was refused")
		}
	})

	t.Run("[GW-UPL-002] refuses one byte over the cap and a zero-byte upload", func(t *testing.T) {
		if WithinSizeCap(MaxUploadBytes + 1) {
			t.Error("an upload over the cap was admitted")
		}
		if WithinSizeCap(0) {
			t.Error("a zero-byte upload was admitted")
		}
	})
}

func TestRateLimiter(t *testing.T) {
	t.Run("[GW-RTL-001] spends the budget and then refuses", func(t *testing.T) {
		limiter := NewRateLimiter(5)
		for i := 0; i < 5; i++ {
			if !limiter.Admit("acme") {
				t.Fatalf("upload %d was refused inside the budget", i+1)
			}
		}
		if limiter.Admit("acme") {
			t.Error("the sixth upload was admitted")
		}
	})

	t.Run("[GW-RTL-001] restores the budget in the next window", func(t *testing.T) {
		limiter := NewRateLimiter(1)
		limiter.Admit("acme")
		limiter.Advance()
		if !limiter.Admit("acme") {
			t.Error("the next window refused the first upload")
		}
	})

	t.Run("[GW-RTL-001] keeps one tenant's budget off another's", func(t *testing.T) {
		limiter := NewRateLimiter(1)
		limiter.Admit("acme")
		if !limiter.Admit("globex") {
			t.Error("one tenant's spending drained another's budget")
		}
	})
}
