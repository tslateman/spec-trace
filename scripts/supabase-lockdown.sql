-- Close the PostgREST door on a Django-owned schema.
-- Django connects as postgres (table owner, bypassrls), so nothing here touches the app.
-- Run: psql "$DATABASE_URL" -X -f scripts/supabase-lockdown.sql

begin;

revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
revoke usage on schema public from anon, authenticated;

alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public revoke all on functions from anon, authenticated;

do $$
declare t text;
begin
  for t in select quote_ident(tablename) from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%s enable row level security', t);
  end loop;
end $$;

commit;

\echo === verify: rows must be 0 / 0
select count(*) as tables_without_rls from pg_tables where schemaname = 'public' and not rowsecurity;
select count(*) as anon_grants from information_schema.role_table_grants
where table_schema = 'public' and grantee in ('anon', 'authenticated');
