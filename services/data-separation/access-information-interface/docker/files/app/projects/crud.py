from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlalchemy import select
from ..models import (
    Projects,
    Rights,
    Roles,
    RolesRights,
    UsersProjectsRoles,
    Data,
    DataProjects,
)
from . import schemas


async def create_project(session: AsyncSession, project: schemas.CreateProject):
    new_project = Projects(name=project.name, description=project.description)
    session.add(new_project)
    await session.commit()
    return new_project


async def get_projects(session: AsyncSession, name: str = None):
    stmt = select(Projects)
    stmt = stmt.filter(Projects.name == name) if name else stmt
    result = await session.execute(stmt)
    return result.scalars().all()


async def create_rights(session: AsyncSession, right: schemas.CreateRight):
    new_right = Rights(
        name=right.name,
        description=right.description,
        claim_key=right.claim_key,
        claim_value=right.claim_value,
    )
    session.add(new_right)
    await session.commit()
    return new_right


async def get_rights(session: AsyncSession, name: str = None):
    stmt = select(Rights)
    stmt = stmt.filter(Rights.name == name) if name else stmt
    result = await session.execute(stmt)
    return result.scalars().all()


async def create_roles(session: AsyncSession, role: schemas.CreateRole):
    new_role = Roles(name=role.name, description=role.description)
    session.add(new_role)
    await session.commit()
    return new_role


async def get_roles(session: AsyncSession, name: str = None):
    stmt = select(Roles)
    stmt = stmt.filter(Roles.name == name) if name else stmt
    result = await session.execute(stmt)
    return result.scalars().all()


async def create_roles_rights_mapping(
    session: AsyncSession, role_id: int, right_id: int
):
    new_role_rights = RolesRights(role_id=role_id, right_id=right_id)
    session.add(new_role_rights)
    await session.commit()
    return True


async def create_users_projects_roles_mapping(
    session: AsyncSession, project_id: int, role_id: int, keycloak_id
):
    new_user_project_role = UsersProjectsRoles(
        project_id=project_id, role_id=role_id, keycloak_id=keycloak_id
    )
    session.add(new_user_project_role)
    await session.commit()
    return True


async def get_data(session: AsyncSession, series_instance_uid: str = None):
    # TODO Should data only be accessible in a project
    stmt = select(Data)
    stmt = stmt.filter(Data.series_instance_uid == series_instance_uid)
    result = await session.execute(stmt)
    return result.scalars().all()


async def create_data(session: AsyncSession, data: schemas.CreateData):
    new_data = Data(
        description=data.description,
        data_type=data.data_type,
        series_instance_uid=data.series_instance_uid,
    )
    session.add(new_data)
    await session.commit()
    return new_data


async def create_data_projects_mapping(
    session: AsyncSession, project_id: int, data_id: int
):
    new_data_projects = DataProjects(project_id=project_id, data_id=data_id)
    session.add(new_data_projects)
    await session.commit()
    return True
