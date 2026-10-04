# AI Analytics Assistant
## Getting the data

The raw data is not stored in this repo (it's in `.gitignore`). To rebuild the database:

1. Download "Superstore Dataset (Final)" by vivek468 from Kaggle: https://www.kaggle.com/datasets/vivek468/superstore-dataset-final and save the zip as `data/raw/superstore.zip`.
2. Unzip it and rename the CSV:
   ```
   unzip data/raw/superstore.zip -d data/raw
   mv "data/raw/Sample - Superstore.csv" data/raw/superstore.csv
   ```
3. Convert it from Windows-1252 to UTF-8:
   ```
   iconv -f WINDOWS-1252 -t UTF-8 data/raw/superstore.csv > data/raw/superstore_utf8.csv
   ```
4. Build the tables (Postgres must be running in the `sales-db` container):
   ```
   docker exec -i sales-db psql -U analyst -d sales < sql/01_staging.sql
   docker exec -i sales-db psql -U analyst -d sales -c "\copy stg_superstore FROM pstdin WITH (FORMAT csv, HEADER true)" < data/raw/superstore_utf8.csv
   docker exec -i sales-db psql -U analyst -d sales < sql/02_clean_tables.sql
   ```