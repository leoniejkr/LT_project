package dicom

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
)

type Repository struct {
	basePath string
}

// zunächst speicherung auf festplatte, später in orthanc
func NewRepository(basePath string) (*Repository, error) {
	if err := os.MkdirAll(basePath, 0755); err != nil {
		return nil, err
	}
	return &Repository{basePath: basePath}, nil
}

func (s *Repository) Save(patientID uint, filename string, r io.Reader) (string, error) {
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

func (s *Repository) SaveAll(patientID uint, files map[string]io.Reader) ([]string, error) {
	var paths []string
	for filename, r := range files {
		path, err := s.Save(patientID, filename, r)
		if err != nil {
			return nil, fmt.Errorf("failed to save %s: %w", filename, err)
		}
		paths = append(paths, path)
	}
	return paths, nil
}
