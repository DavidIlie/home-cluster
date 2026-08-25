\set ON_ERROR_STOP on

BEGIN;

SELECT 'CREATE ROLE employee_hub_plausible_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'employee_hub_plausible_owner'
) \gexec

ALTER ROLE employee_hub_plausible_owner
  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

SELECT format(
  'CREATE ROLE employee_hub_plausible_reader LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
  :'reader_password'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'employee_hub_plausible_reader'
) \gexec

ALTER ROLE employee_hub_plausible_reader
  LOGIN PASSWORD :'reader_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

ALTER ROLE employee_hub_plausible_reader SET default_transaction_read_only TO true;
ALTER ROLE employee_hub_plausible_reader SET statement_timeout TO '5s';
ALTER ROLE employee_hub_plausible_reader SET lock_timeout TO '2s';
ALTER ROLE employee_hub_plausible_reader SET idle_in_transaction_session_timeout TO '5s';
ALTER ROLE employee_hub_plausible_reader SET search_path TO pg_catalog;
ALTER ROLE employee_hub_plausible_reader SET temp_file_limit TO '16MB';

SELECT format('REVOKE %I FROM employee_hub_plausible_owner', granted_role.rolname)
FROM pg_catalog.pg_auth_members AS membership
JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
WHERE member_role.rolname = 'employee_hub_plausible_owner'
\gexec

SELECT format('REVOKE %I FROM employee_hub_plausible_reader', granted_role.rolname)
FROM pg_catalog.pg_auth_members AS membership
JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
WHERE member_role.rolname = 'employee_hub_plausible_reader'
\gexec

CREATE SCHEMA IF NOT EXISTS employee_hub AUTHORIZATION employee_hub_plausible_owner;
ALTER SCHEMA employee_hub OWNER TO employee_hub_plausible_owner;
REVOKE ALL ON SCHEMA employee_hub FROM PUBLIC;
GRANT USAGE ON SCHEMA employee_hub TO employee_hub_plausible_reader;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM employee_hub_plausible_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM employee_hub_plausible_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM employee_hub_plausible_reader;
REVOKE ALL ON ALL PROCEDURES IN SCHEMA public FROM employee_hub_plausible_reader;

GRANT USAGE ON SCHEMA public TO employee_hub_plausible_owner;
GRANT SELECT (domain, team_id) ON TABLE public.sites TO employee_hub_plausible_owner;
GRANT SELECT (id, identifier) ON TABLE public.teams TO employee_hub_plausible_owner;

CREATE OR REPLACE FUNCTION employee_hub.list_sites()
RETURNS TABLE(domain text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
  SELECT s.domain::pg_catalog.text
  FROM public.sites AS s
  JOIN public.teams AS t ON t.id = s.team_id
  WHERE t.identifier = 'a4ef2a8b-e3be-4b65-b1aa-601352802d01'::pg_catalog.uuid
  ORDER BY pg_catalog.lower(s.domain::pg_catalog.text), s.domain
$function$;

ALTER FUNCTION employee_hub.list_sites() OWNER TO employee_hub_plausible_owner;
REVOKE ALL ON FUNCTION employee_hub.list_sites() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION employee_hub.list_sites() TO employee_hub_plausible_reader;

DO $check$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM public.teams
    WHERE identifier = 'a4ef2a8b-e3be-4b65-b1aa-601352802d01'::pg_catalog.uuid
  ) THEN
    RAISE EXCEPTION 'Bostan Enterprise Plausible team does not exist';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_class AS relation
    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
      AND pg_catalog.has_table_privilege(
        'employee_hub_plausible_reader',
        relation.oid,
        'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
      )
  ) THEN
    RAISE EXCEPTION 'Employee Hub reader has effective public relation access';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_class AS sequence
    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = sequence.relnamespace
    WHERE namespace.nspname = 'public'
      AND CASE
        WHEN sequence.relkind = 'S' THEN pg_catalog.has_sequence_privilege(
          'employee_hub_plausible_reader',
          sequence.oid,
          'SELECT,UPDATE,USAGE'
        )
        ELSE false
      END
  ) THEN
    RAISE EXCEPTION 'Employee Hub reader has effective public sequence access';
  END IF;

  IF pg_catalog.has_schema_privilege(
    'employee_hub_plausible_reader',
    'public',
    'CREATE'
  ) OR pg_catalog.has_schema_privilege(
    'employee_hub_plausible_reader',
    'employee_hub',
    'CREATE'
  ) THEN
    RAISE EXCEPTION 'Employee Hub reader can create durable schema objects';
  END IF;

  IF pg_catalog.has_schema_privilege(
    'employee_hub_plausible_owner',
    'public',
    'CREATE'
  ) THEN
    RAISE EXCEPTION 'Employee Hub function owner can create objects in public';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_proc AS function
    WHERE function.prosecdef
      AND function.oid <> 'employee_hub.list_sites()'::pg_catalog.regprocedure
      AND pg_catalog.has_function_privilege(
        'employee_hub_plausible_reader',
        function.oid,
        'EXECUTE'
      )
  ) THEN
    RAISE EXCEPTION 'Employee Hub reader can execute an unexpected SECURITY DEFINER function';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_auth_members AS membership
    JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
    WHERE member_role.rolname IN (
      'employee_hub_plausible_owner',
      'employee_hub_plausible_reader'
    )
  ) THEN
    RAISE EXCEPTION 'Employee Hub database roles retain inherited memberships';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles AS reader
    WHERE reader.rolname = 'employee_hub_plausible_reader'
      AND (
        EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspowner = reader.oid)
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_class WHERE relowner = reader.oid)
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_proc WHERE proowner = reader.oid)
        OR EXISTS (SELECT 1 FROM pg_catalog.pg_type WHERE typowner = reader.oid)
      )
  ) THEN
    RAISE EXCEPTION 'Employee Hub reader owns database objects';
  END IF;

  -- The shared database grants CONNECT and TEMPORARY to PUBLIC. TEMPORARY is
  -- session-local; durable data remains protected by the effective relation
  -- checks above, default read-only transactions, and the SECURITY DEFINER audit.
  IF NOT pg_catalog.has_database_privilege(
    'employee_hub_plausible_reader',
    pg_catalog.current_database(),
    'CONNECT'
  ) THEN
    RAISE EXCEPTION 'Employee Hub reader cannot connect to the Plausible database';
  END IF;

  IF NOT pg_catalog.has_function_privilege(
    'employee_hub_plausible_reader',
    'employee_hub.list_sites()',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Employee Hub reader cannot execute list_sites()';
  END IF;
END
$check$;

COMMIT;
