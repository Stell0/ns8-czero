// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
// Catch regexes accepted by Python tests but rejected by Core's Go validator.
package main

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

func check(value any) error {
	switch v := value.(type) {
	case map[string]any:
		for key, child := range v {
			if key == "pattern" {
				pattern, ok := child.(string)
				if !ok {
					return fmt.Errorf("pattern must be a string")
				}
				if _, err := regexp.Compile(pattern); err != nil {
					return err
				}
			}
			if err := check(child); err != nil {
				return err
			}
		}
	case []any:
		for _, child := range v {
			if err := check(child); err != nil {
				return err
			}
		}
	}
	return nil
}

func main() {
	err := filepath.WalkDir("imageroot/actions", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() || !strings.HasPrefix(d.Name(), "validate-") || !strings.HasSuffix(path, ".json") {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		var schema any
		if err := json.Unmarshal(data, &schema); err != nil {
			return err
		}
		if err := check(schema); err != nil {
			return fmt.Errorf("%s: %w", path, err)
		}
		return nil
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("Action schema patterns compile with Core's Go regex engine")
}
