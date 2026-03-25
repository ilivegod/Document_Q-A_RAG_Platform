# ######DOCKER########

# Start Postgres for the first time

docker run -d --name docqa-postgres -e POSTGRES_USER=docqa -e POSTGRES_PASSWORD=docqa123 -e POSTGRES_DB=docqa_db -p 5432:5432 pgvector/pgvector:pg16

# Stop the container

docker stop docqa-postgres

# Start it again (after stopping)

docker start docqa-postgres

# Check running containers

# run fastApi

uvicorn app.main:app --reload

docker ps

# See container logs

docker logs docqa-postgres

# Connect to Postgres directly (useful for debugging)

docker exec -it docqa-postgres psql -U docqa -d docqa_db

# Remove the container completely (you'll lose data)

docker rm -f docqa-postgres

# ###### ALEMBIC

# Initialize alembic in your project (only once)

alembic init alembic

# Generate a migration after changing models

alembic revision --autogenerate -m "describe what changed"

# Apply all pending migrations

alembic upgrade head

# Undo the last migration

alembic downgrade -1

# See current migration status

alembic current

# See migration history

alembic history
