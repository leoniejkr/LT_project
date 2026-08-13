package platform

import (
	"fmt"
	"os"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

func InitDB() (*gorm.DB, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "host=localhost user=user password=trustai dbname=trustai port=5432 sslmode=disable TimeZone=Europe/Berlin"
	}

	var db *gorm.DB
	var err error

	for i := range 30 {
		db, err = gorm.Open(postgres.Open(dsn), &gorm.Config{})
		if err == nil {
			return db, nil
		}

		fmt.Fprintf(os.Stderr, "database not ready (attempt %d/30): %v\n", i+1, err)
		time.Sleep(1 * time.Second)
	}

	return nil, fmt.Errorf("giving up after 30 attempts: %w", err)
}
