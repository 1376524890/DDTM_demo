package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type server struct {
	bin          string
	artifactsDir string
	secret       []byte
	timeout      time.Duration
}

func main() {
	port := env("PROVER_PORT", "8081")
	s := &server{
		bin:          env("PROVER_BIN", "/app/bin/v1prove"),
		artifactsDir: env("ARTIFACTS_DIR", "/app/artifacts/v1"),
		secret:       []byte(requiredEnv("PROVER_SHARED_SECRET")),
		timeout:      2 * time.Minute,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "scheme": "Groth16", "curve": "BN254"})
	})
	mux.HandleFunc("POST /v1/proofs/{proofType}", s.handleProof)

	httpServer := &http.Server{
		Addr:              ":" + port,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      3 * time.Minute,
		IdleTimeout:       60 * time.Second,
	}
	log.Printf("DDTM prover listening on :%s", port)
	log.Fatal(httpServer.ListenAndServe())
}

func (s *server) handleProof(w http.ResponseWriter, r *http.Request) {
	proofType := r.PathValue("proofType")
	if proofType != "commitments" && proofType != "quality" && proofType != "key" && proofType != "delivery" {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "unknown proof type"})
		return
	}

	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "request body too large or unreadable"})
		return
	}
	if err := s.authenticate(r, body); err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": err.Error()})
		return
	}
	if !json.Valid(body) {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "body must be valid JSON"})
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), s.timeout)
	defer cancel()
	cmd := exec.CommandContext(
		ctx,
		s.bin,
		"--type", proofType,
		"--artifacts", filepath.Clean(s.artifactsDir),
	)
	cmd.Stdin = strings.NewReader(string(body))
	output, err := cmd.CombinedOutput()
	if ctx.Err() == context.DeadlineExceeded {
		writeJSON(w, http.StatusGatewayTimeout, map[string]string{"error": "proof generation timed out"})
		return
	}
	if err != nil {
		log.Printf("proof generation failed: %v: %s", err, output)
		writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": strings.TrimSpace(string(output))})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(output)
}

func (s *server) authenticate(r *http.Request, body []byte) error {
	timestampText := r.Header.Get("X-DDTM-Timestamp")
	signatureText := r.Header.Get("X-DDTM-Signature")
	if timestampText == "" || signatureText == "" {
		return fmt.Errorf("missing service authentication headers")
	}
	timestamp, err := strconv.ParseInt(timestampText, 10, 64)
	if err != nil {
		return fmt.Errorf("invalid timestamp")
	}
	if delta := time.Since(time.Unix(timestamp, 0)); delta > time.Minute || delta < -time.Minute {
		return fmt.Errorf("request timestamp outside allowed window")
	}
	provided, err := hex.DecodeString(signatureText)
	if err != nil {
		return fmt.Errorf("invalid signature encoding")
	}
	mac := hmac.New(sha256.New, s.secret)
	_, _ = mac.Write([]byte(timestampText))
	_, _ = mac.Write([]byte("."))
	_, _ = mac.Write(body)
	if !hmac.Equal(provided, mac.Sum(nil)) {
		return fmt.Errorf("invalid service signature")
	}
	return nil
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func env(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func requiredEnv(name string) string {
	value := os.Getenv(name)
	if value == "" {
		log.Fatalf("required environment variable %s is not set", name)
	}
	return value
}
