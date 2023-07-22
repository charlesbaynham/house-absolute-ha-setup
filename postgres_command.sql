-- Copied from https://community.home-assistant.io/t/home-assistant-db-vs-mariadb/224295/4  
-- Edited to reflect new table structure 
-- Changes: 
-- 1. Reflect new states format 
-- 2. Archive attributes too

-- This SQL file will set up the required tables. It's only needed if you make a new database from
-- scratch, in which case these commands should be run manually in the database query interface.
-- Otherwise, the functions etc persist so this is just stored for reference. 

-- *** TABLES ***

-- Analytics Table Definition  
CREATE TABLE IF NOT EXISTS public.states_archive (  
state_id integer NOT NULL, 
entity_id character varying(255) COLLATE pg_catalog."default",  
state character varying(255) COLLATE pg_catalog."default",  
attributes text COLLATE pg_catalog."default",  
event_id integer,  
last_changed timestamp with time zone,  
last_changed_ts float,
last_updated timestamp with time zone,  
last_updated_ts float,
old_state_id integer,
attributes_id integer,
context_id character varying(36) COLLATE pg_catalog."default",  
context_user_id character varying(36) COLLATE pg_catalog."default",  
context_parent_id character varying(36) COLLATE pg_catalog."default",  
origin_idx smallint
);

-- Analytics state attributes table 
CREATE TABLE IF NOT EXISTS public.state_attributes_archive 
( 
attributes_id integer NOT NULL, 
hash bigint, 
shared_attrs text COLLATE pg_catalog."default" 
); 


-- Function to insert into analytics table the the row being added to states table  
create or replace function trigger_on_states()  
returns trigger language plpgsql  
as $function$  
begin  
insert into states_archive  
select new.*;  
return new;  
end; $function$;  


-- Create useful indexes for analytics  
create index IF NOT EXISTS ix_states_archive_last_updated 
ON states_archive using btree 
(last_updated DESC);  
CREATE INDEX IF NOT EXISTS ix_state_attributes_archive_hash 
ON public.state_attributes_archive USING btree 
(hash ASC NULLS LAST); 


-- *** TRIGGERS *** 


-- Trigger that is fired on each insert to states table  
create or replace trigger trigger_on_states  
before insert  
on states  
for each row  
execute procedure trigger_on_states();  


-- Ditto triggers for attributes 
create or replace function trigger_on_attrs()  
returns trigger language plpgsql  
as $function$  
begin  
insert into state_attributes_archive  
select new.*;  
return new;  
end; $function$;  
-- Trigger that is fired on each insert to attrs table  
create or replace trigger trigger_on_attrs  
before insert  
on state_attributes  
for each row  
execute procedure trigger_on_attrs();  