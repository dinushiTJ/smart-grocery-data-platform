# Metabase on a glibc base so the DuckDB driver's native library can load.
#
# The official image is Alpine (musl). DuckDB ships a glibc-linked JNI library,
# which fails there with "Error loading shared library libstdc++.so.6", and the
# gcompat shim crashes the JVM in native code. Re-hosting the same metabase.jar
# on Debian is the smallest reliable fix, and it keeps the upstream version pinned.
FROM metabase/metabase:v0.63.3 AS upstream

FROM eclipse-temurin:25-jre-noble

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash curl libstdc++6 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# run_metabase.sh drops privileges to this user when started as root.
RUN groupadd -r metabase && useradd -r -g metabase metabase

COPY --from=upstream /app /app

ENV MB_PLUGINS_DIR=/plugins
EXPOSE 3000
WORKDIR /app
ENTRYPOINT ["/app/run_metabase.sh"]
