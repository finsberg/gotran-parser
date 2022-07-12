from __future__ import annotations

from collections import defaultdict
from typing import Optional

import lark

from . import atoms


def remove_quotes(s: str) -> str:
    return s.replace("'", "").replace('"', "")


def find_assignment_component(s) -> Optional[str]:
    component = None
    if isinstance(s, lark.Token) and s.type == "COMPONENT_NAME":
        component = remove_quotes(str(s))
    return component


def find_assignments(s, component: Optional[str] = None) -> list[atoms.Assignment]:
    if isinstance(s, lark.Tree):
        return [
            atoms.Assignment(
                lhs=str(s.children[0]),
                rhs=atoms.Expression(tree=s.children[1]),
                component=component,
            ),
        ]

    return []


class TreeToODE(lark.Transformer):
    def states(self, s) -> tuple[atoms.State, ...]:
        return tuple(
            [
                atoms.State(name=str(p[0]), ic=float(p[1]), component=s[0], info=s[1])
                for p in s[2:]
            ],
        )

    def parameters(self, s) -> tuple[atoms.Parameter, ...]:
        component = s[0]
        if component is not None:
            component = remove_quotes(str(component))
        return tuple(
            [
                atoms.Parameter(name=str(p[0]), value=float(p[1]), component=component)
                for p in s[1:]
            ],
        )

    def pair(self, s):
        return s

    def expressions(self, s) -> tuple[atoms.Assignment, ...]:
        component = find_assignment_component(s[0])
        assignments = []

        for si in s:
            assignments.extend(find_assignments(si, component=component))

        return tuple(assignments)

    def ode(self, s) -> tuple[atoms.Component, ...]:

        # FIXME: Could use Enum here
        mapping = {
            atoms.Parameter: "parameters",
            atoms.Assignment: "assignments",
            atoms.State: "states",
        }

        components: dict[Optional[str], dict[str, set[atoms.Atoms]]] = defaultdict(
            lambda: {atom: set() for atom in mapping.values()},
        )

        for line in s:  # Each line in the block
            for atom in line:  # State, Parameters or Assignment
                components[atom.component][mapping[type(atom)]].add(atom)

        # Make sets frozen
        frozen_components: dict[Optional[str], dict[str, frozenset[atoms.Atoms]]] = {}
        for component_name, component_values in components.items():
            frozen_components[component_name] = {}
            for atom_name, atom_values in component_values.items():
                frozen_components[component_name][atom_name] = frozenset(atom_values)

        # FIXME: Need to somehow tell the type checker that each of the inner dictionaries
        # are actually of the correct type.
        return tuple(
            [
                atoms.Component(name=key, **value)  # type: ignore
                for key, value in frozen_components.items()
            ],
        )