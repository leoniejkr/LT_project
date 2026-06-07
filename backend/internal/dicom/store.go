package dicom

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
)

type Store struct {
	basePath string
}

func NewStore(basePath string) (*Store, error) {
	// dicom bilder werden zunächst auf festplatte gespeichert
	if err := os.MkdirAll(basePath, 0755); err != nil {
		return nil, err
	}
	return &Store{basePath: basePath}, nil
}

func (s *Store) Save(patientID uint, filename string, r io.Reader) (string, error) {
	// Erstelle Patienten-spezifischen Unterordner
	patientDir := filepath.Join(s.basePath, fmt.Sprintf("patient_%d", patientID))
	if err := os.MkdirAll(patientDir, 0755); err != nil {
		return "", err
	}

	dstPath := filepath.Join(patientDir, filename)
	dst, err := os.Create(dstPath)
	if err != nil {
		return "", err
	}
	defer dst.Close()

	if _, err := io.Copy(dst, r); err != nil {
		return "", err
	}

	return dstPath, nil
}
