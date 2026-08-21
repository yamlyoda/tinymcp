# Схема стенда зашита в образ, а не примонтирована: путь к уроку содержит ':',
# а docker-демон не принимает такой путь в bind-mount.
FROM postgres:16-alpine

COPY init.sql /docker-entrypoint-initdb.d/init.sql
