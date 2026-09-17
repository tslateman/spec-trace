// Package gateway admits uploads that the document pipeline can process.
package gateway

const MaxUploadBytes = 100 << 20

var supportedMediaTypes = map[string]bool{
	"application/pdf": true,
	"image/png":       true,
	"image/jpeg":      true,
	"image/tiff":      true,
}

// Accepts reports whether the pipeline can process the given media type.
func Accepts(mediaType string) bool {
	return supportedMediaTypes[mediaType]
}

// WithinSizeCap reports whether an upload of size bytes fits the per-upload cap.
func WithinSizeCap(size int64) bool {
	return size > 0 && size <= MaxUploadBytes
}

// RateLimiter holds each tenant to a fixed number of uploads per window.
type RateLimiter struct {
	budget int
	window int
	starts map[string]int
	seen   map[string]int
}

// NewRateLimiter returns a limiter granting each tenant budget uploads per window.
func NewRateLimiter(budget int) *RateLimiter {
	return &RateLimiter{budget: budget, starts: map[string]int{}, seen: map[string]int{}}
}

// Admit records an upload for tenant and reports whether its budget allowed it.
func (l *RateLimiter) Admit(tenant string) bool {
	if l.seen[tenant] != l.window {
		l.seen[tenant] = l.window
		l.starts[tenant] = 0
	}
	if l.starts[tenant] >= l.budget {
		return false
	}
	l.starts[tenant]++
	return true
}

// Advance opens the next window, restoring every tenant's budget.
func (l *RateLimiter) Advance() {
	l.window++
}
