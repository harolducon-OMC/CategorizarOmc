-- Fase 2: ejecutar solo después de asignar dueño a todos los estudios históricos.
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.studies WHERE owner_id IS NULL) THEN
        RAISE EXCEPTION
            'Hay estudios sin owner_id. Asígnales un usuario antes de exigir el campo.';
    END IF;
END $$;

ALTER TABLE public.studies
    ALTER COLUMN owner_id SET NOT NULL;

COMMIT;
