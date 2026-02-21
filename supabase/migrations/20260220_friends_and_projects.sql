-- Friends & Shared Projects schema for AshAI
-- Run this in Supabase SQL editor or via supabase db push

-- ============================================================
-- profiles — cached user info
-- ============================================================
create table if not exists profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    display_name text not null default '',
    created_at timestamptz not null default now()
);
create index if not exists idx_profiles_email on profiles(email);

-- Auto-create profile on sign-up
create or replace function public.handle_new_user()
returns trigger as $$
begin
    insert into public.profiles (id, email, display_name)
    values (new.id, new.email, split_part(new.email, '@', 1));
    return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ============================================================
-- friendships
-- ============================================================
create table if not exists friendships (
    id uuid primary key default gen_random_uuid(),
    requester_id uuid not null references profiles(id) on delete cascade,
    addressee_id uuid not null references profiles(id) on delete cascade,
    status text not null default 'pending',  -- pending | accepted | declined
    created_at timestamptz not null default now(),
    unique(requester_id, addressee_id)
);
create index if not exists idx_friendships_requester on friendships(requester_id);
create index if not exists idx_friendships_addressee on friendships(addressee_id);

-- ============================================================
-- projects + project_members
-- ============================================================
create table if not exists projects (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text default '',
    owner_id uuid not null references profiles(id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists project_members (
    project_id uuid not null references projects(id) on delete cascade,
    user_id uuid not null references profiles(id) on delete cascade,
    role text not null default 'editor',  -- owner | editor | viewer
    joined_at timestamptz not null default now(),
    primary key (project_id, user_id)
);
create index if not exists idx_project_members_user on project_members(user_id);

-- ============================================================
-- invites — shareable links for friends or projects
-- ============================================================
create table if not exists invites (
    id uuid primary key default gen_random_uuid(),
    code text unique not null default encode(gen_random_bytes(12), 'hex'),
    type text not null,  -- 'friend' or 'project'
    creator_id uuid not null references profiles(id) on delete cascade,
    project_id uuid references projects(id) on delete cascade,
    max_uses int default 1,
    uses int default 0,
    expires_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists idx_invites_code on invites(code);

-- ============================================================
-- RLS policies
-- ============================================================

-- Enable RLS on all tables
alter table profiles enable row level security;
alter table friendships enable row level security;
alter table projects enable row level security;
alter table project_members enable row level security;
alter table invites enable row level security;

-- profiles: anyone authenticated can SELECT; users can UPDATE only their own row
create policy "profiles_select" on profiles
    for select to authenticated
    using (true);

create policy "profiles_update_own" on profiles
    for update to authenticated
    using (id = auth.uid());

-- friendships: users can see their own friendships
create policy "friendships_select" on friendships
    for select to authenticated
    using (requester_id = auth.uid() or addressee_id = auth.uid());

create policy "friendships_insert" on friendships
    for insert to authenticated
    with check (requester_id = auth.uid());

create policy "friendships_update" on friendships
    for update to authenticated
    using (addressee_id = auth.uid());

-- projects: users can see projects they're members of
create policy "projects_select" on projects
    for select to authenticated
    using (
        exists (
            select 1 from project_members
            where project_members.project_id = projects.id
            and project_members.user_id = auth.uid()
        )
    );

create policy "projects_insert" on projects
    for insert to authenticated
    with check (owner_id = auth.uid());

create policy "projects_update" on projects
    for update to authenticated
    using (owner_id = auth.uid());

create policy "projects_delete" on projects
    for delete to authenticated
    using (owner_id = auth.uid());

-- project_members: users can see members of their projects
create policy "project_members_select" on project_members
    for select to authenticated
    using (
        exists (
            select 1 from project_members pm
            where pm.project_id = project_members.project_id
            and pm.user_id = auth.uid()
        )
    );

create policy "project_members_insert" on project_members
    for insert to authenticated
    with check (
        exists (
            select 1 from projects
            where projects.id = project_members.project_id
            and projects.owner_id = auth.uid()
        )
        or user_id = auth.uid()
    );

create policy "project_members_delete" on project_members
    for delete to authenticated
    using (
        user_id = auth.uid()
        or exists (
            select 1 from projects
            where projects.id = project_members.project_id
            and projects.owner_id = auth.uid()
        )
    );

-- invites: creator can manage; anyone authenticated can read by code
create policy "invites_select_own" on invites
    for select to authenticated
    using (creator_id = auth.uid());

create policy "invites_select_by_code" on invites
    for select to authenticated
    using (true);

create policy "invites_insert" on invites
    for insert to authenticated
    with check (creator_id = auth.uid());

create policy "invites_delete" on invites
    for delete to authenticated
    using (creator_id = auth.uid());
