# Branch strategy

The repository has two independent compatibility branches because Calliope
0.6 and 0.7 use different array schemas and incompatible dependency sets.

| Branch | Calliope | Data format | Conda environment |
| --- | --- | --- | --- |
| `stable/calliope-0.6.10` | 0.6.10 | trusted pickle fixtures | dashboard and model envs |
| `migration/calliope-0.7.0-dev7` | 0.7.0.dev7 | native grouped NetCDF | one combined env |

The tag `internship-original` marks the unchanged internship commit. The
`main` branch remains at that commit until one compatibility branch is chosen
as the new default.

Switch branches with:

```bash
git switch stable/calliope-0.6.10
git switch migration/calliope-0.7.0-dev7
```

Do not merge the helper and environment files wholesale between these branches.
Shared UI fixes can be cherry-picked when they do not depend on Calliope's data
schema. Run the branch's own `make setup` and `make check` after switching.
