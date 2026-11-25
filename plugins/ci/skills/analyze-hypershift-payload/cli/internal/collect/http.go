package collect

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// get bounds each response, including the decompressed body. The client owns
// per-request timeouts and the caller owns cancellation of the whole run.
func get(ctx context.Context, client *http.Client, address string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, address, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GET %s: %s", address, resp.Status)
	}
	const limit = 32 << 20
	data, err := io.ReadAll(io.LimitReader(resp.Body, limit+1))
	if err == nil && len(data) > limit {
		return nil, fmt.Errorf("GET %s: response exceeds %d bytes", address, limit)
	}
	return data, err
}

func getJSON(ctx context.Context, client *http.Client, address string, dest any) error {
	data, err := get(ctx, client, address)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(data, dest); err != nil {
		return fmt.Errorf("GET %s: %w", address, err)
	}
	return nil
}
