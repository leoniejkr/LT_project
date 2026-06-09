package platform

import (
	"os"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

func InitDB() (*gorm.DB, error) {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "host=localhost user=user password=trustai dbname=trustai port=5432 sslmode=disable TimeZone=Europe/Berlin"
	}

	return gorm.Open(postgres.Open(dsn), &gorm.Config{})
}
