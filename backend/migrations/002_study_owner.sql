-- Fase 1: agrega dueño a cada estudio existente sin adivinar a quién pertenecen
-- los estudios históricos. Ejecutar en Neon antes de desplegar el backend nuevo.
BEGIN;

ALTER TABLE public.studies
    ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_studies_owner_id_users'
          AND conrelid = 'public.studies'::regclass
    ) THEN
        ALTER TABLE public.studies
            ADD CONSTRAINT fk_studies_owner_id_users
            FOREIGN KEY (owner_id)
            REFERENCES public.users(id)
            ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_studies_owner_id
    ON public.studies(owner_id);

COMMIT;

-- Los estudios históricos quedan con owner_id = NULL y no serán visibles desde
-- la aplicación hasta asignarles explícitamente un usuario. Consulta primero:
--
-- SELECT id, email FROM public.users ORDER BY email;
-- SELECT id, name, created_at FROM public.studies
-- WHERE owner_id IS NULL ORDER BY created_at;
--
-- Para cada relación confirmada, ejecuta (sustituye los dos valores):
--
-- UPDATE public.studies
-- SET owner_id = '<USER_ID_CONFIRMADO>'
-- WHERE id = '<STUDY_ID_CONFIRMADO>' AND owner_id IS NULL;
--
-- Cuando todos los estudios históricos tengan dueño, ejecuta la migración
-- 003_enforce_study_owner.sql para hacer owner_id obligatorio en PostgreSQL.
