# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/xmap/cora/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                                     |    Stmts |     Miss |   Branch |   BrPart |     Cover |   Missing |
|----------------------------------------------------------------------------------------- | -------: | -------: | -------: | -------: | --------: | --------: |
| src/cora/\_\_init\_\_.py                                                                 |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/\_\_init\_\_.py                                                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/\_bootstrap.py                                                           |        2 |        2 |        0 |        0 |      0.0% |     14-16 |
| src/cora/access/\_projections.py                                                         |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/adapters/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/adapters/event\_store\_principal\_liveness\_lookup.py                    |       13 |        0 |        2 |        0 |    100.0% |           |
| src/cora/access/aggregates/\_\_init\_\_.py                                               |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/aggregates/actor/\_\_init\_\_.py                                         |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/aggregates/actor/events.py                                               |       47 |        0 |       18 |        0 |    100.0% |           |
| src/cora/access/aggregates/actor/evolver.py                                              |       19 |        0 |        4 |        0 |    100.0% |           |
| src/cora/access/aggregates/actor/profile.py                                              |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/aggregates/actor/read.py                                                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/aggregates/actor/state.py                                                |       40 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/errors.py                                                                |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/\_\_init\_\_.py                                                 |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/deactivate\_actor/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/deactivate\_actor/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/deactivate\_actor/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/access/features/deactivate\_actor/handler.py                                    |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/access/features/deactivate\_actor/route.py                                      |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/deactivate\_actor/tool.py                                       |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/forget\_actor/\_\_init\_\_.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/forget\_actor/command.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/forget\_actor/decider.py                                        |        7 |        0 |        2 |        0 |    100.0% |           |
| src/cora/access/features/forget\_actor/handler.py                                        |       40 |        0 |        4 |        0 |    100.0% |           |
| src/cora/access/features/forget\_actor/route.py                                          |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/forget\_actor/tool.py                                           |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/get\_actor/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/get\_actor/handler.py                                           |       31 |        0 |        4 |        0 |    100.0% |           |
| src/cora/access/features/get\_actor/query.py                                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/get\_actor/route.py                                             |       19 |        0 |        2 |        0 |    100.0% |           |
| src/cora/access/features/get\_actor/tool.py                                              |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/access/features/list\_actors/\_\_init\_\_.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/list\_actors/handler.py                                         |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/list\_actors/query.py                                           |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/list\_actors/route.py                                           |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/list\_actors/tool.py                                            |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/reactivate\_actor/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/reactivate\_actor/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/reactivate\_actor/decider.py                                    |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/access/features/reactivate\_actor/handler.py                                    |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/access/features/reactivate\_actor/route.py                                      |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/reactivate\_actor/tool.py                                       |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/register\_actor/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/register\_actor/command.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/register\_actor/decider.py                                      |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/access/features/register\_actor/handler.py                                      |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/access/features/register\_actor/route.py                                        |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/features/register\_actor/tool.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/projections/\_\_init\_\_.py                                              |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/projections/summary.py                                                   |       28 |        0 |       10 |        0 |    100.0% |           |
| src/cora/access/routes.py                                                                |       65 |        0 |        8 |        0 |    100.0% |           |
| src/cora/access/tools.py                                                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/access/wire.py                                                                  |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/\_\_init\_\_.py                                                           |       29 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/\_agent\_seed.py                                                          |       53 |        0 |        2 |        0 |    100.0% |           |
| src/cora/agent/\_agent\_update\_handler.py                                               |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/\_bootstrap.py                                                            |        2 |        2 |        0 |        0 |      0.0% |     11-13 |
| src/cora/agent/\_budget\_gate.py                                                         |       49 |        0 |       16 |        0 |    100.0% |           |
| src/cora/agent/\_gpu\_metrics.py                                                         |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/agent/\_language\_model\_update\_handler.py                                     |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/\_model\_ref.py                                                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/\_pricing\_bridge.py                                                      |       26 |        1 |        6 |        1 |     93.8% |        91 |
| src/cora/agent/\_projections.py                                                          |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/\_seeded\_fleet.py                                                        |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/\_subscriber\_lease.py                                                    |       54 |        0 |       16 |        0 |    100.0% |           |
| src/cora/agent/\_subscribers.py                                                          |       47 |        0 |       10 |        0 |    100.0% |           |
| src/cora/agent/adapters/\_\_init\_\_.py                                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/adapters/anthropic\_llm.py                                                |      102 |        0 |       26 |        0 |    100.0% |           |
| src/cora/agent/adapters/argo\_llm.py                                                     |       44 |        1 |        6 |        0 |     98.0% |       234 |
| src/cora/agent/adapters/budget\_spend\_guard.py                                          |       40 |        0 |       18 |        0 |    100.0% |           |
| src/cora/agent/adapters/local\_llm.py                                                    |       68 |        2 |        8 |        1 |     96.1% |   262-263 |
| src/cora/agent/adapters/openai\_compatible\_backend.py                                   |       73 |        7 |       14 |        1 |     88.5% |81-82, 95-98, 179 |
| src/cora/agent/adapters/postgres\_language\_model\_lookup.py                             |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/agent/aggregates/\_\_init\_\_.py                                                |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/aggregates/agent/\_\_init\_\_.py                                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/aggregates/agent/events.py                                                |       84 |        0 |       34 |        0 |    100.0% |           |
| src/cora/agent/aggregates/agent/evolver.py                                               |       44 |        0 |       20 |        0 |    100.0% |           |
| src/cora/agent/aggregates/agent/read.py                                                  |       22 |        5 |        2 |        0 |     70.8% |     78-82 |
| src/cora/agent/aggregates/agent/state.py                                                 |      239 |        0 |       28 |        0 |    100.0% |           |
| src/cora/agent/aggregates/language\_model/\_\_init\_\_.py                                |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/aggregates/language\_model/events.py                                      |       72 |        3 |       24 |        1 |     95.8% |   407-409 |
| src/cora/agent/aggregates/language\_model/evolver.py                                     |       29 |        0 |       10 |        0 |    100.0% |           |
| src/cora/agent/aggregates/language\_model/read.py                                        |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/aggregates/language\_model/state.py                                       |      116 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/build\_llm.py                                                             |       54 |        0 |       24 |        0 |    100.0% |           |
| src/cora/agent/errors.py                                                                 |       51 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/\_\_init\_\_.py                                                  |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/announce\_language\_model\_retirement/\_\_init\_\_.py            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/announce\_language\_model\_retirement/command.py                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/announce\_language\_model\_retirement/decider.py                 |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/announce\_language\_model\_retirement/handler.py                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/announce\_language\_model\_retirement/route.py                   |       19 |        3 |        0 |        0 |     84.2% | 51-52, 96 |
| src/cora/agent/features/announce\_language\_model\_retirement/tool.py                    |       19 |        3 |        0 |        0 |     84.2% |     64-75 |
| src/cora/agent/features/approve\_language\_model/\_\_init\_\_.py                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/approve\_language\_model/command.py                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/approve\_language\_model/decider.py                              |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/agent/features/approve\_language\_model/handler.py                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/approve\_language\_model/route.py                                |       13 |        3 |        0 |        0 |     76.9% | 23-24, 62 |
| src/cora/agent/features/approve\_language\_model/tool.py                                 |       17 |        3 |        0 |        0 |     82.4% |     42-49 |
| src/cora/agent/features/define\_agent/\_\_init\_\_.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/define\_agent/command.py                                         |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/define\_agent/decider.py                                         |       20 |        0 |        8 |        0 |    100.0% |           |
| src/cora/agent/features/define\_agent/handler.py                                         |       44 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/define\_agent/route.py                                           |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/define\_agent/tool.py                                            |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/define\_language\_model/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/define\_language\_model/command.py                               |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/define\_language\_model/decider.py                               |       23 |        1 |        4 |        0 |     96.3% |       111 |
| src/cora/agent/features/define\_language\_model/handler.py                               |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/agent/features/define\_language\_model/route.py                                 |       22 |        4 |        0 |        0 |     81.8% |123-124, 175-193 |
| src/cora/agent/features/define\_language\_model/tool.py                                  |       19 |        3 |        0 |        0 |     84.2% |   128-146 |
| src/cora/agent/features/deprecate\_agent/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_agent/command.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_agent/decider.py                                      |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_agent/handler.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_agent/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_agent/tool.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_language\_model/\_\_init\_\_.py                       |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_language\_model/command.py                            |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_language\_model/decider.py                            |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_language\_model/handler.py                            |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/deprecate\_language\_model/route.py                              |       16 |        3 |        0 |        0 |     81.2% | 41-42, 83 |
| src/cora/agent/features/deprecate\_language\_model/tool.py                               |       18 |        3 |        0 |        0 |     83.3% |     55-62 |
| src/cora/agent/features/dismiss\_event\_in\_reaction/\_\_init\_\_.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/dismiss\_event\_in\_reaction/command.py                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/dismiss\_event\_in\_reaction/decider.py                          |       27 |        0 |        6 |        0 |    100.0% |           |
| src/cora/agent/features/dismiss\_event\_in\_reaction/handler.py                          |       47 |        0 |        8 |        0 |    100.0% |           |
| src/cora/agent/features/dismiss\_event\_in\_reaction/route.py                            |       19 |        1 |        0 |        0 |     94.7% |       152 |
| src/cora/agent/features/dismiss\_event\_in\_reaction/tool.py                             |       17 |        1 |        0 |        0 |     94.1% |        75 |
| src/cora/agent/features/get\_agent/\_\_init\_\_.py                                       |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/get\_agent/handler.py                                            |       32 |        1 |        6 |        1 |     94.7% |       123 |
| src/cora/agent/features/get\_agent/query.py                                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/get\_agent/route.py                                              |       34 |        0 |        2 |        0 |    100.0% |           |
| src/cora/agent/features/get\_agent/tool.py                                               |       34 |        0 |        2 |        0 |    100.0% |           |
| src/cora/agent/features/grant\_tool\_to\_agent/\_\_init\_\_.py                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/grant\_tool\_to\_agent/command.py                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/grant\_tool\_to\_agent/decider.py                                |       14 |        0 |        8 |        0 |    100.0% |           |
| src/cora/agent/features/grant\_tool\_to\_agent/handler.py                                |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/grant\_tool\_to\_agent/route.py                                  |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/grant\_tool\_to\_agent/tool.py                                   |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/list\_at\_risk\_results/\_\_init\_\_.py                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/list\_at\_risk\_results/handler.py                               |       35 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/list\_at\_risk\_results/query.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/list\_at\_risk\_results/route.py                                 |       23 |        5 |        0 |        0 |     78.3% |71, 91-92, 124-130 |
| src/cora/agent/features/list\_at\_risk\_results/tool.py                                  |       22 |        3 |        0 |        0 |     86.4% |     76-83 |
| src/cora/agent/features/promote\_caution\_proposal/\_\_init\_\_.py                       |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/promote\_caution\_proposal/command.py                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/promote\_caution\_proposal/decider.py                            |       49 |        3 |       16 |        1 |     93.8% |125, 154-155 |
| src/cora/agent/features/promote\_caution\_proposal/handler.py                            |       76 |        0 |       14 |        0 |    100.0% |           |
| src/cora/agent/features/promote\_caution\_proposal/route.py                              |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/promote\_caution\_proposal/tool.py                               |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/regenerate\_run\_debrief/\_\_init\_\_.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/regenerate\_run\_debrief/command.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/regenerate\_run\_debrief/context.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/regenerate\_run\_debrief/decider.py                              |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/agent/features/regenerate\_run\_debrief/handler.py                              |      114 |        5 |       36 |        3 |     94.7% |221, 516, 519, 522-523 |
| src/cora/agent/features/regenerate\_run\_debrief/route.py                                |       24 |        1 |        2 |        1 |     92.3% |        70 |
| src/cora/agent/features/regenerate\_run\_debrief/tool.py                                 |       17 |        2 |        0 |        0 |     88.2% |     72-82 |
| src/cora/agent/features/resume\_agent/\_\_init\_\_.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/resume\_agent/command.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/resume\_agent/decider.py                                         |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/resume\_agent/handler.py                                         |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/resume\_agent/route.py                                           |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/resume\_agent/tool.py                                            |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/retire\_language\_model/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/retire\_language\_model/command.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/retire\_language\_model/decider.py                               |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/agent/features/retire\_language\_model/handler.py                               |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/retire\_language\_model/route.py                                 |       17 |        3 |        0 |        0 |     82.4% | 42-43, 86 |
| src/cora/agent/features/retire\_language\_model/tool.py                                  |       18 |        3 |        0 |        0 |     83.3% |     53-60 |
| src/cora/agent/features/revoke\_tool\_from\_agent/\_\_init\_\_.py                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/revoke\_tool\_from\_agent/command.py                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/revoke\_tool\_from\_agent/decider.py                             |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/agent/features/revoke\_tool\_from\_agent/handler.py                             |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/revoke\_tool\_from\_agent/route.py                               |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/revoke\_tool\_from\_agent/tool.py                                |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/suspend\_agent/\_\_init\_\_.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/suspend\_agent/command.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/suspend\_agent/decider.py                                        |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/suspend\_agent/handler.py                                        |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/suspend\_agent/route.py                                          |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/suspend\_agent/tool.py                                           |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_budget/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_budget/command.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_budget/decider.py                                 |       14 |        0 |        8 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_budget/handler.py                                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_budget/route.py                                   |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_budget/tool.py                                    |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_target\_plan/\_\_init\_\_.py                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_target\_plan/command.py                           |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_target\_plan/decider.py                           |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_target\_plan/handler.py                           |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_target\_plan/route.py                             |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/update\_agent\_target\_plan/tool.py                              |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/version\_agent/\_\_init\_\_.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/version\_agent/command.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/version\_agent/decider.py                                        |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/features/version\_agent/handler.py                                        |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/version\_agent/route.py                                          |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/features/version\_agent/tool.py                                           |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/projections/\_\_init\_\_.py                                               |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/projections/agent.py                                                      |       21 |        0 |        6 |        0 |    100.0% |           |
| src/cora/agent/projections/language\_model.py                                            |       28 |        0 |       10 |        0 |    100.0% |           |
| src/cora/agent/promote\_seeded\_fleet.py                                                 |       45 |        0 |       10 |        0 |    100.0% |           |
| src/cora/agent/prompts/\_\_init\_\_.py                                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/prompts/caution\_drafter.py                                               |       49 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/prompts/run\_debrief.py                                                   |       35 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/routes.py                                                                 |       56 |        2 |        8 |        0 |     96.9% |   143-144 |
| src/cora/agent/seed.py                                                                   |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_authority\_revocation\_holder.py                                    |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_calibration\_watcher.py                                             |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_campaign\_watcher.py                                                |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_capture\_baseline\_reader.py                                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_capture\_progress\_feeder.py                                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_capture\_scan\_ingestor.py                                          |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_caution\_drafter.py                                                 |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_caution\_promoter.py                                                |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_clearance\_expirer.py                                               |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_clearance\_watcher.py                                               |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_durable\_copy\_registrar.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_experiment\_steerer.py                                              |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_language\_models.py                                                 |       46 |        0 |        4 |        0 |    100.0% |           |
| src/cora/agent/seed\_procedure\_watcher.py                                               |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_ratification\_enforcer.py                                           |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_run\_initiator.py                                                   |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_run\_supervisor.py                                                  |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/seed\_run\_witness.py                                                     |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/subscribers/\_\_init\_\_.py                                               |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/subscribers/\_ratification\_shared.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/agent/subscribers/\_terminal\_run\_helpers.py                                   |       41 |        0 |       14 |        0 |    100.0% |           |
| src/cora/agent/subscribers/authority\_revocation\_holder.py                              |       98 |        0 |       16 |        0 |    100.0% |           |
| src/cora/agent/subscribers/caution\_drafter.py                                           |      191 |        0 |       44 |        0 |    100.0% |           |
| src/cora/agent/subscribers/caution\_promoter.py                                          |      136 |        3 |       30 |        1 |     97.6% |217-222, 415 |
| src/cora/agent/subscribers/ratification\_hold.py                                         |       65 |       10 |       12 |        3 |     83.1% |75, 81-82, 90-91, 114-115, 141-143 |
| src/cora/agent/subscribers/ratification\_release.py                                      |       74 |       11 |       18 |        4 |     83.7% |96, 99, 108-109, 117-118, 138-139, 180-182 |
| src/cora/agent/subscribers/run\_debriefer.py                                             |      160 |        2 |       30 |        1 |     98.4% |   982-986 |
| src/cora/agent/tools.py                                                                  |       48 |        1 |        2 |        1 |     96.0% |       148 |
| src/cora/agent/wire.py                                                                   |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/api/\_\_init\_\_.py                                                             |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/api/\_agent\_decision\_signing.py                                               |       10 |        0 |        2 |        0 |    100.0% |           |
| src/cora/api/\_bleps\_supply\_observer.py                                                |      158 |        3 |       62 |        3 |     97.3% |472-\>471, 622-623, 847 |
| src/cora/api/\_calibration\_watcher.py                                                   |       59 |        1 |       10 |        1 |     97.1% |       145 |
| src/cora/api/\_campaign\_watcher.py                                                      |       61 |        0 |       12 |        0 |    100.0% |           |
| src/cora/api/\_capture\_baseline\_reader.py                                              |       86 |        2 |       20 |        0 |     98.1% |  194, 227 |
| src/cora/api/\_capture\_experiment\_identity\_reader.py                                  |       68 |        2 |       14 |        0 |     97.6% |  189, 218 |
| src/cora/api/\_capture\_observer.py                                                      |      200 |        2 |       58 |        1 |     98.1% |   428-429 |
| src/cora/api/\_capture\_progress\_feeder.py                                              |       78 |        6 |       16 |        0 |     93.6% |226, 268, 289-292 |
| src/cora/api/\_capture\_scan\_ingestor.py                                                |      164 |        0 |       32 |        0 |    100.0% |           |
| src/cora/api/\_clearance\_expirer.py                                                     |      109 |        1 |       14 |        0 |     99.2% |       297 |
| src/cora/api/\_clearance\_watcher.py                                                     |       79 |        1 |       22 |        1 |     98.0% |       162 |
| src/cora/api/\_conduct\_run\_route.py                                                    |       88 |        3 |       16 |        3 |     94.2% |208, 211, 260 |
| src/cora/api/\_conduct\_run\_tool.py                                                     |       33 |        0 |        0 |        0 |    100.0% |           |
| src/cora/api/\_distribution\_materializer.py                                             |       40 |        2 |        6 |        1 |     93.5% |   188-191 |
| src/cora/api/\_durable\_copy\_registrar.py                                               |       73 |        0 |       18 |        0 |    100.0% |           |
| src/cora/api/\_durable\_copy\_verdict.py                                                 |       56 |        0 |       18 |        0 |    100.0% |           |
| src/cora/api/\_durable\_distribution.py                                                  |       57 |        0 |        2 |        0 |    100.0% |           |
| src/cora/api/\_durable\_distribution\_driver.py                                          |      105 |        2 |       28 |        1 |     97.7% |   532-536 |
| src/cora/api/\_durable\_distribution\_sweep.py                                           |       52 |        0 |        4 |        0 |    100.0% |           |
| src/cora/api/\_edge\_conductor.py                                                        |       85 |        7 |        6 |        1 |     91.2% |161-164, 315, 317, 323 |
| src/cora/api/\_enclosure\_permit\_observer.py                                            |       78 |        2 |       20 |        1 |     94.9% |   187-188 |
| src/cora/api/\_experiment\_steerer.py                                                    |      106 |        2 |       32 |        3 |     96.4% |416-\>420, 465-\>475, 487-488 |
| src/cora/api/\_flag\_watcher.py                                                          |       69 |        0 |       12 |        0 |    100.0% |           |
| src/cora/api/\_inference\_recorder.py                                                    |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/api/\_procedure\_watcher.py                                                     |       78 |        0 |       22 |        0 |    100.0% |           |
| src/cora/api/\_readiness.py                                                              |       39 |        0 |        4 |        0 |    100.0% |           |
| src/cora/api/\_run\_initiator.py                                                         |      151 |       14 |       30 |        5 |     88.4% |157-158, 187-188, 233, 253, 300, 305-306, 327-\>316, 391-392, 399-406 |
| src/cora/api/\_run\_phase\_conduct.py                                                    |       36 |        1 |        4 |        1 |     95.0% |       191 |
| src/cora/api/\_run\_supervisor.py                                                        |      483 |       27 |      192 |       21 |     92.6% |280, 298, 305, 460, 665-666, 826-827, 884, 910, 913, 919, 921, 947-948, 1131-\>1141, 1317, 1320, 1323, 1326, 1328-1329, 1332, 1335, 1338, 1534, 1543-\>1509, 1629, 1652 |
| src/cora/api/\_run\_witness.py                                                           |      379 |       22 |      124 |        6 |     94.0% |618, 869-873, 914, 976, 1007, 1050, 1067, 1069, 1094, 1116, 1202, 1297, 1367-1369, 1371-\>1373, 1378, 1389-1392, 1397 |
| src/cora/api/capture\_watch\_preflight.py                                                |      217 |        3 |       82 |        1 |     98.7% |534, 642-643 |
| src/cora/api/errors.py                                                                   |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/api/main.py                                                                     |      430 |        7 |       66 |        4 |     97.8% |393-\>392, 818-819, 1287-1299, 1477-\>1482, 1484-\>1487 |
| src/cora/api/middleware.py                                                               |       31 |        0 |        6 |        0 |    100.0% |           |
| src/cora/api/pilot\_seed.py                                                              |      353 |       43 |       64 |       10 |     85.4% |297-302, 320-326, 336-337, 370-372, 415-416, 459-496, 561-562, 573-574, 651, 655, 667-668, 753-755, 925-955 |
| src/cora/api/protected\_resource\_metadata.py                                            |       30 |        0 |        8 |        1 |     97.4% | 127-\>125 |
| src/cora/api/record\_bundle\_export.py                                                   |       86 |        2 |        2 |        0 |     97.7% |   358-359 |
| src/cora/budget/\_\_init\_\_.py                                                          |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/\_allocation\_update\_handler.py                                         |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/\_projections.py                                                         |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/\_subscribers.py                                                         |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/adapters/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/adapters/postgres\_allocation\_lookup.py                                 |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/budget/aggregates/\_\_init\_\_.py                                               |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/aggregates/allocation/\_\_init\_\_.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/aggregates/allocation/events.py                                          |       52 |        4 |       18 |        2 |     91.4% |283, 311-313 |
| src/cora/budget/aggregates/allocation/evolver.py                                         |       28 |        0 |       10 |        0 |    100.0% |           |
| src/cora/budget/aggregates/allocation/read.py                                            |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/aggregates/allocation/state.py                                           |       79 |        0 |        2 |        0 |    100.0% |           |
| src/cora/budget/errors.py                                                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/activate\_allocation/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/activate\_allocation/command.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/activate\_allocation/decider.py                                 |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/budget/features/activate\_allocation/handler.py                                 |       36 |        0 |        4 |        0 |    100.0% |           |
| src/cora/budget/features/activate\_allocation/route.py                                   |       13 |        3 |        0 |        0 |     76.9% | 23-24, 62 |
| src/cora/budget/features/activate\_allocation/tool.py                                    |       17 |        3 |        0 |        0 |     82.4% |     42-49 |
| src/cora/budget/features/grant\_allocation/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/grant\_allocation/command.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/grant\_allocation/decider.py                                    |       11 |        0 |        2 |        0 |    100.0% |           |
| src/cora/budget/features/grant\_allocation/handler.py                                    |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/budget/features/grant\_allocation/route.py                                      |       20 |        4 |        0 |        0 |     80.0% |72-73, 120-132 |
| src/cora/budget/features/grant\_allocation/tool.py                                       |       18 |        3 |        0 |        0 |     83.3% |     79-91 |
| src/cora/budget/features/seal\_allocation/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/seal\_allocation/command.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/seal\_allocation/decider.py                                     |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/budget/features/seal\_allocation/handler.py                                     |       45 |        0 |        4 |        0 |    100.0% |           |
| src/cora/budget/features/seal\_allocation/route.py                                       |       17 |        3 |        0 |        0 |     82.4% | 42-43, 89 |
| src/cora/budget/features/seal\_allocation/tool.py                                        |       18 |        3 |        0 |        0 |     83.3% |     50-57 |
| src/cora/budget/features/update\_allocation\_ceiling/\_\_init\_\_.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/update\_allocation\_ceiling/command.py                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/update\_allocation\_ceiling/decider.py                          |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/budget/features/update\_allocation\_ceiling/handler.py                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/update\_allocation\_ceiling/route.py                            |       15 |        3 |        0 |        0 |     80.0% | 38-39, 85 |
| src/cora/budget/features/update\_allocation\_ceiling/tool.py                             |       17 |        3 |        0 |        0 |     82.4% |     48-55 |
| src/cora/budget/features/void\_allocation/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/void\_allocation/command.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/void\_allocation/decider.py                                     |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/budget/features/void\_allocation/handler.py                                     |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/features/void\_allocation/route.py                                       |       16 |        3 |        0 |        0 |     81.2% | 39-40, 86 |
| src/cora/budget/features/void\_allocation/tool.py                                        |       18 |        3 |        0 |        0 |     83.3% |     49-56 |
| src/cora/budget/projections/\_\_init\_\_.py                                              |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/projections/allocation.py                                                |       28 |        0 |       10 |        0 |    100.0% |           |
| src/cora/budget/routes.py                                                                |       36 |       11 |        8 |        0 |     75.0% |57-58, 65-67, 75-76, 90-91, 104-105 |
| src/cora/budget/subscribers/\_\_init\_\_.py                                              |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/subscribers/allocation\_sealer.py                                        |       67 |        4 |       14 |        3 |     91.4% |170-\>exit, 191-198, 255-259 |
| src/cora/budget/tools.py                                                                 |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/budget/wire.py                                                                  |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/\_\_init\_\_.py                                                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/\_bootstrap.py                                                      |        2 |        2 |        0 |        0 |      0.0% |     11-13 |
| src/cora/calibration/\_calibration\_dtos.py                                              |       26 |        2 |        8 |        1 |     91.2% |   124-125 |
| src/cora/calibration/\_projections.py                                                    |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/aggregates/\_\_init\_\_.py                                          |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/aggregates/calibration/\_\_init\_\_.py                              |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/aggregates/calibration/events.py                                    |       78 |        3 |       22 |        1 |     96.0% |   454-470 |
| src/cora/calibration/aggregates/calibration/evolver.py                                   |       23 |        3 |        6 |        1 |     86.2% |   121-123 |
| src/cora/calibration/aggregates/calibration/read.py                                      |       23 |        5 |        2 |        0 |     72.0% |   125-129 |
| src/cora/calibration/aggregates/calibration/state.py                                     |      112 |        1 |       10 |        2 |     97.5% |403, 513-\>516 |
| src/cora/calibration/errors.py                                                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/\_\_init\_\_.py                                            |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/append\_calibration\_revision/\_\_init\_\_.py              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/append\_calibration\_revision/command.py                   |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/append\_calibration\_revision/decider.py                   |       35 |        0 |       10 |        1 |     97.8% |165-\>exit |
| src/cora/calibration/features/append\_calibration\_revision/handler.py                   |       37 |        2 |        4 |        1 |     92.7% |   117-126 |
| src/cora/calibration/features/append\_calibration\_revision/route.py                     |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/append\_calibration\_revision/tool.py                      |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/define\_calibration/\_\_init\_\_.py                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/define\_calibration/command.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/define\_calibration/decider.py                             |       26 |        0 |        6 |        0 |    100.0% |           |
| src/cora/calibration/features/define\_calibration/handler.py                             |       32 |        2 |        2 |        1 |     91.2% |   105-113 |
| src/cora/calibration/features/define\_calibration/route.py                               |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/define\_calibration/tool.py                                |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/get\_calibration/\_\_init\_\_.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/get\_calibration/handler.py                                |       32 |        1 |        6 |        1 |     94.7% |       122 |
| src/cora/calibration/features/get\_calibration/query.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/get\_calibration/route.py                                  |       29 |        0 |        2 |        0 |    100.0% |           |
| src/cora/calibration/features/get\_calibration/tool.py                                   |       30 |        1 |        2 |        0 |     96.9% |        65 |
| src/cora/calibration/features/list\_calibrations/\_\_init\_\_.py                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/list\_calibrations/handler.py                              |       23 |        1 |        0 |        0 |     95.7% |        86 |
| src/cora/calibration/features/list\_calibrations/query.py                                |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/list\_calibrations/route.py                                |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/list\_calibrations/tool.py                                 |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/publish\_revision/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/publish\_revision/command.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/publish\_revision/decider.py                               |       32 |        0 |       14 |        0 |    100.0% |           |
| src/cora/calibration/features/publish\_revision/handler.py                               |       76 |        0 |        6 |        0 |    100.0% |           |
| src/cora/calibration/features/publish\_revision/route.py                                 |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/features/publish\_revision/tool.py                                  |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/projections/\_\_init\_\_.py                                         |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/projections/calibration.py                                          |       32 |        3 |       10 |        3 |     85.7% |92, 97, 155 |
| src/cora/calibration/quantities/\_\_init\_\_.py                                          |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/quantities/blade\_throw\_scale.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/quantities/detector\_pixel\_size.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/quantities/effective\_thickness.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/quantities/energy\_position\_curve.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/quantities/index\_position\_table.py                                |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/quantities/magnification.py                                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/quantities/rotation\_center.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/routes.py                                                           |       36 |        0 |        8 |        0 |    100.0% |           |
| src/cora/calibration/tools.py                                                            |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/calibration/wire.py                                                             |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/\_\_init\_\_.py                                                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/\_bootstrap.py                                                         |        2 |        2 |        0 |        0 |      0.0% |     14-16 |
| src/cora/campaign/\_campaign\_update\_handler.py                                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/\_projections.py                                                       |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/aggregates/\_\_init\_\_.py                                             |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/aggregates/campaign/\_\_init\_\_.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/aggregates/campaign/events.py                                          |       93 |        0 |       34 |        0 |    100.0% |           |
| src/cora/campaign/aggregates/campaign/evolver.py                                         |       39 |        0 |       18 |        0 |    100.0% |           |
| src/cora/campaign/aggregates/campaign/read.py                                            |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/aggregates/campaign/state.py                                           |      137 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/errors.py                                                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/\_\_init\_\_.py                                               |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/abandon\_campaign/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/abandon\_campaign/command.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/abandon\_campaign/decider.py                                  |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/abandon\_campaign/handler.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/abandon\_campaign/route.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/abandon\_campaign/tool.py                                     |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/add\_run\_to\_campaign/\_\_init\_\_.py                        |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/add\_run\_to\_campaign/command.py                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/add\_run\_to\_campaign/context.py                             |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/add\_run\_to\_campaign/decider.py                             |       19 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/add\_run\_to\_campaign/handler.py                             |       44 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/add\_run\_to\_campaign/route.py                               |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/add\_run\_to\_campaign/tool.py                                |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/close\_campaign/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/close\_campaign/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/close\_campaign/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/campaign/features/close\_campaign/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/close\_campaign/route.py                                      |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/close\_campaign/tool.py                                       |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/declare\_campaign\_steering/\_\_init\_\_.py                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/declare\_campaign\_steering/command.py                        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/declare\_campaign\_steering/decider.py                        |       19 |        0 |       12 |        0 |    100.0% |           |
| src/cora/campaign/features/declare\_campaign\_steering/handler.py                        |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/declare\_campaign\_steering/route.py                          |       32 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/declare\_campaign\_steering/tool.py                           |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/get\_campaign/\_\_init\_\_.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/get\_campaign/handler.py                                      |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/campaign/features/get\_campaign/query.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/get\_campaign/route.py                                        |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/campaign/features/get\_campaign/tool.py                                         |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/campaign/features/hold\_campaign/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/hold\_campaign/command.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/hold\_campaign/decider.py                                     |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/hold\_campaign/handler.py                                     |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/hold\_campaign/route.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/hold\_campaign/tool.py                                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/list\_campaigns/\_\_init\_\_.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/list\_campaigns/handler.py                                    |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/list\_campaigns/query.py                                      |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/list\_campaigns/route.py                                      |       41 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/list\_campaigns/tool.py                                       |       42 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/register\_campaign/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/register\_campaign/command.py                                 |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/register\_campaign/decider.py                                 |       17 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/register\_campaign/handler.py                                 |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/campaign/features/register\_campaign/route.py                                   |       27 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/register\_campaign/tool.py                                    |       23 |        1 |        2 |        1 |     92.0% |        36 |
| src/cora/campaign/features/remove\_run\_from\_campaign/\_\_init\_\_.py                   |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/remove\_run\_from\_campaign/command.py                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/remove\_run\_from\_campaign/context.py                        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/remove\_run\_from\_campaign/decider.py                        |       21 |        0 |        6 |        0 |    100.0% |           |
| src/cora/campaign/features/remove\_run\_from\_campaign/handler.py                        |       44 |        2 |        6 |        1 |     94.0% |    90-100 |
| src/cora/campaign/features/remove\_run\_from\_campaign/route.py                          |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/remove\_run\_from\_campaign/tool.py                           |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/resume\_campaign/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/resume\_campaign/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/resume\_campaign/decider.py                                   |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/campaign/features/resume\_campaign/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/resume\_campaign/route.py                                     |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/resume\_campaign/tool.py                                      |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/start\_campaign/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/start\_campaign/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/start\_campaign/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/campaign/features/start\_campaign/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/start\_campaign/route.py                                      |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/features/start\_campaign/tool.py                                       |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/projections/\_\_init\_\_.py                                            |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/projections/campaign.py                                                |       46 |        0 |       16 |        0 |    100.0% |           |
| src/cora/campaign/routes.py                                                              |       42 |        0 |        8 |        0 |    100.0% |           |
| src/cora/campaign/tools.py                                                               |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/campaign/wire.py                                                                |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/\_\_init\_\_.py                                                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/\_bootstrap.py                                                          |        2 |        2 |        0 |        0 |      0.0% |     14-16 |
| src/cora/caution/\_caution\_dtos.py                                                      |       12 |        0 |        2 |        0 |    100.0% |           |
| src/cora/caution/\_projections.py                                                        |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/adapters/\_\_init\_\_.py                                                |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/adapters/postgres\_caution\_lookup.py                                   |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/aggregates/\_\_init\_\_.py                                              |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/aggregates/caution/\_\_init\_\_.py                                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/aggregates/caution/events.py                                            |       60 |        0 |       16 |        0 |    100.0% |           |
| src/cora/caution/aggregates/caution/evolver.py                                           |       21 |        0 |        6 |        0 |    100.0% |           |
| src/cora/caution/aggregates/caution/invariants.py                                        |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/caution/aggregates/caution/read.py                                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/aggregates/caution/state.py                                             |       96 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/errors.py                                                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/\_\_init\_\_.py                                                |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/get\_caution/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/get\_caution/handler.py                                        |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/caution/features/get\_caution/query.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/get\_caution/route.py                                          |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/caution/features/get\_caution/tool.py                                           |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/caution/features/list\_cautions/\_\_init\_\_.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/list\_cautions/handler.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/list\_cautions/query.py                                        |       27 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/list\_cautions/route.py                                        |       57 |        3 |       14 |        0 |     93.0% |   161-163 |
| src/cora/caution/features/list\_cautions/tool.py                                         |       58 |        5 |       14 |        2 |     87.5% |103, 109, 113-115 |
| src/cora/caution/features/register\_caution/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/register\_caution/command.py                                   |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/register\_caution/decider.py                                   |       13 |        0 |        2 |        0 |    100.0% |           |
| src/cora/caution/features/register\_caution/handler.py                                   |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/caution/features/register\_caution/route.py                                     |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/register\_caution/tool.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/retire\_caution/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/retire\_caution/command.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/retire\_caution/decider.py                                     |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/caution/features/retire\_caution/handler.py                                     |       33 |        0 |        4 |        0 |    100.0% |           |
| src/cora/caution/features/retire\_caution/route.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/retire\_caution/tool.py                                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/supersede\_caution/\_\_init\_\_.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/supersede\_caution/command.py                                  |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/supersede\_caution/context.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/supersede\_caution/decider.py                                  |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/supersede\_caution/handler.py                                  |       41 |        0 |        4 |        0 |    100.0% |           |
| src/cora/caution/features/supersede\_caution/route.py                                    |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/features/supersede\_caution/tool.py                                     |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/projections/\_\_init\_\_.py                                             |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/projections/caution.py                                                  |       27 |        0 |        6 |        0 |    100.0% |           |
| src/cora/caution/routes.py                                                               |       36 |        0 |        8 |        0 |    100.0% |           |
| src/cora/caution/tools.py                                                                |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/caution/wire.py                                                                 |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/\_\_init\_\_.py                                                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/\_bootstrap.py                                                             |       85 |       10 |       28 |        6 |     85.8% |156-162, 229-230, 268-272, 276-280, 286-290, 327-\>249 |
| src/cora/data/\_ingest.py                                                                |       34 |        1 |        2 |        1 |     94.4% |       107 |
| src/cora/data/\_projections.py                                                           |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/\_remote\_scan\_probe.py                                                   |      100 |        4 |       20 |        0 |     96.7% |   309-312 |
| src/cora/data/adapters/\_\_init\_\_.py                                                   |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/adapters/\_file\_uri.py                                                    |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/adapters/\_ssh\_probe.py                                                   |       66 |        0 |       14 |        0 |    100.0% |           |
| src/cora/data/adapters/capture\_path\_locator.py                                         |       36 |        0 |       12 |        0 |    100.0% |           |
| src/cora/data/adapters/data\_exchange\_scan\_reader.py                                   |      136 |       13 |       30 |        2 |     91.0% |138-147, 268-269, 307-308, 312, 316-317, 320, 347-348 |
| src/cora/data/adapters/http\_range\_checksum.py                                          |       62 |       11 |       16 |        5 |     79.5% |97, 100-101, 105, 110, 121-129, 131, 136, 145 |
| src/cora/data/adapters/in\_memory\_distribution\_lookup.py                               |       18 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/adapters/posix\_checksum.py                                                |       60 |        1 |       14 |        1 |     97.3% |       147 |
| src/cora/data/adapters/postgres\_dataset\_distribution\_lookup.py                        |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/adapters/postgres\_distribution\_lookup.py                                 |       24 |        2 |        4 |        2 |     85.7% |    37, 53 |
| src/cora/data/adapters/rocrate12\_serializer.py                                          |       28 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/adapters/ssh\_data\_exchange\_scan\_reader.py                              |       44 |        0 |        8 |        0 |    100.0% |           |
| src/cora/data/adapters/ssh\_locate\_probe.py                                             |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/adapters/ssh\_posix\_checksum\_computer.py                                 |       26 |        0 |        4 |        0 |    100.0% |           |
| src/cora/data/adapters/stub\_edition\_serializer.py                                      |       16 |        1 |        0 |        0 |     93.8% |       121 |
| src/cora/data/aggregates/\_\_init\_\_.py                                                 |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/acquisition/\_\_init\_\_.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/acquisition/events.py                                           |       37 |        0 |        6 |        0 |    100.0% |           |
| src/cora/data/aggregates/acquisition/evolver.py                                          |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/aggregates/acquisition/read.py                                             |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/acquisition/state.py                                            |      122 |        1 |       36 |        1 |     98.7% |       343 |
| src/cora/data/aggregates/attestation/\_\_init\_\_.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/attestation/events.py                                           |       44 |       20 |        4 |        0 |     54.2% |   136-180 |
| src/cora/data/aggregates/attestation/evolver.py                                          |       38 |       30 |       14 |        0 |     15.4% |64-89, 101-116, 133-136 |
| src/cora/data/aggregates/attestation/read.py                                             |       10 |        3 |        0 |        0 |     70.0% |     22-24 |
| src/cora/data/aggregates/attestation/state.py                                            |       99 |        0 |       18 |        0 |    100.0% |           |
| src/cora/data/aggregates/dataset/\_\_init\_\_.py                                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/dataset/events.py                                               |       55 |        0 |       14 |        0 |    100.0% |           |
| src/cora/data/aggregates/dataset/evolver.py                                              |       24 |        0 |        8 |        0 |    100.0% |           |
| src/cora/data/aggregates/dataset/read.py                                                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/dataset/state.py                                                |      225 |        0 |       32 |        0 |    100.0% |           |
| src/cora/data/aggregates/distribution/\_\_init\_\_.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/distribution/\_backfill\_errors.py                              |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/distribution/\_namespaces.py                                    |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/distribution/events.py                                          |       43 |        3 |       10 |        1 |     92.5% |   326-328 |
| src/cora/data/aggregates/distribution/evolver.py                                         |       23 |        0 |        6 |        0 |    100.0% |           |
| src/cora/data/aggregates/distribution/read.py                                            |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/distribution/state.py                                           |      153 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/aggregates/edition/\_\_init\_\_.py                                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/aggregates/edition/events.py                                               |       67 |       10 |       22 |        2 |     84.3% |361-369, 398-411 |
| src/cora/data/aggregates/edition/evolver.py                                              |       39 |        2 |       14 |        1 |     94.3% |     49-50 |
| src/cora/data/aggregates/edition/read.py                                                 |       11 |        3 |        0 |        0 |     72.7% |     22-24 |
| src/cora/data/aggregates/edition/state.py                                                |      200 |        2 |       22 |        0 |     99.1% |   520-524 |
| src/cora/data/errors.py                                                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/\_\_init\_\_.py                                                   |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/add\_dataset\_to\_edition/\_\_init\_\_.py                         |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/add\_dataset\_to\_edition/command.py                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/add\_dataset\_to\_edition/context.py                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/add\_dataset\_to\_edition/decider.py                              |       16 |        0 |        8 |        0 |    100.0% |           |
| src/cora/data/features/add\_dataset\_to\_edition/handler.py                              |       39 |        0 |        6 |        0 |    100.0% |           |
| src/cora/data/features/add\_dataset\_to\_edition/route.py                                |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/add\_dataset\_to\_edition/tool.py                                 |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/demote\_dataset/\_\_init\_\_.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/demote\_dataset/command.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/demote\_dataset/decider.py                                        |       15 |        0 |        8 |        0 |    100.0% |           |
| src/cora/data/features/demote\_dataset/handler.py                                        |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/features/demote\_dataset/route.py                                          |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/demote\_dataset/tool.py                                           |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_dataset/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_dataset/command.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_dataset/decider.py                                       |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/data/features/discard\_dataset/handler.py                                       |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/features/discard\_dataset/route.py                                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_dataset/tool.py                                          |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_distribution/\_\_init\_\_.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_distribution/command.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_distribution/context.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_distribution/decider.py                                  |       19 |        0 |        8 |        0 |    100.0% |           |
| src/cora/data/features/discard\_distribution/handler.py                                  |       42 |        1 |        6 |        1 |     95.8% |       126 |
| src/cora/data/features/discard\_distribution/route.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/discard\_distribution/tool.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/get\_dataset/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/get\_dataset/handler.py                                           |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/features/get\_dataset/query.py                                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/get\_dataset/route.py                                             |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/features/get\_dataset/tool.py                                              |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/features/ingest\_scan/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/ingest\_scan/command.py                                           |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/ingest\_scan/handler.py                                           |      118 |        7 |       46 |        9 |     89.0% |236, 279, 282, 285-289, 451-\>453, 453-\>455, 459-\>461, 461-\>465, 471 |
| src/cora/data/features/ingest\_scan/route.py                                             |       24 |        1 |        0 |        0 |     95.8% |       163 |
| src/cora/data/features/ingest\_scan/tool.py                                              |       20 |        1 |        0 |        0 |     95.0% |       102 |
| src/cora/data/features/list\_datasets/\_\_init\_\_.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/list\_datasets/handler.py                                         |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/list\_datasets/query.py                                           |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/list\_datasets/route.py                                           |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/list\_datasets/tool.py                                            |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/mark\_distribution\_stale/\_\_init\_\_.py                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/mark\_distribution\_stale/command.py                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/mark\_distribution\_stale/decider.py                              |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/data/features/mark\_distribution\_stale/handler.py                              |       34 |        0 |        4 |        0 |    100.0% |           |
| src/cora/data/features/mark\_distribution\_stale/route.py                                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/mark\_distribution\_stale/tool.py                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/promote\_dataset/\_\_init\_\_.py                                  |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/promote\_dataset/command.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/promote\_dataset/context.py                                       |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/promote\_dataset/decider.py                                       |       24 |        0 |       16 |        0 |    100.0% |           |
| src/cora/data/features/promote\_dataset/handler.py                                       |       40 |        0 |        8 |        1 |     97.9% | 148-\>146 |
| src/cora/data/features/promote\_dataset/route.py                                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/promote\_dataset/tool.py                                          |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/publish\_edition/\_\_init\_\_.py                                  |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/publish\_edition/command.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/publish\_edition/context.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/publish\_edition/decider.py                                       |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/data/features/publish\_edition/handler.py                                       |       80 |       10 |       20 |        5 |     85.0% |132, 149, 157-158, 168, 180, 200-203 |
| src/cora/data/features/publish\_edition/route.py                                         |       14 |        1 |        0 |        0 |     92.9% |        71 |
| src/cora/data/features/publish\_edition/tool.py                                          |       18 |        1 |        0 |        0 |     94.4% |        45 |
| src/cora/data/features/record\_acquisition/\_\_init\_\_.py                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_acquisition/command.py                                    |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_acquisition/context.py                                    |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_acquisition/decider.py                                    |       24 |        0 |        8 |        0 |    100.0% |           |
| src/cora/data/features/record\_acquisition/handler.py                                    |       47 |        0 |       10 |        0 |    100.0% |           |
| src/cora/data/features/record\_acquisition/route.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_acquisition/tool.py                                       |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_attestation/\_\_init\_\_.py                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_attestation/command.py                                    |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_attestation/context.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/record\_attestation/decider.py                                    |       45 |        0 |       26 |        1 |     98.6% | 222-\>255 |
| src/cora/data/features/record\_attestation/handler.py                                    |       70 |        2 |       18 |        0 |     97.7% |   159-161 |
| src/cora/data/features/record\_attestation/route.py                                      |       20 |        1 |        0 |        0 |     95.0% |       143 |
| src/cora/data/features/record\_attestation/tool.py                                       |       19 |        1 |        0 |        0 |     94.7% |        83 |
| src/cora/data/features/register\_dataset/\_\_init\_\_.py                                 |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_dataset/command.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_dataset/context.py                                      |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_dataset/decider.py                                      |       38 |        0 |       18 |        0 |    100.0% |           |
| src/cora/data/features/register\_dataset/handler.py                                      |       61 |        0 |       20 |        0 |    100.0% |           |
| src/cora/data/features/register\_dataset/route.py                                        |       28 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_dataset/tool.py                                         |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_distribution/\_\_init\_\_.py                            |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_distribution/command.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_distribution/context.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_distribution/decider.py                                 |       35 |        0 |       12 |        0 |    100.0% |           |
| src/cora/data/features/register\_distribution/handler.py                                 |       41 |        0 |        6 |        0 |    100.0% |           |
| src/cora/data/features/register\_distribution/route.py                                   |       23 |        1 |        0 |        0 |     95.7% |       234 |
| src/cora/data/features/register\_distribution/tool.py                                    |       20 |        1 |        0 |        0 |     95.0% |       150 |
| src/cora/data/features/register\_edition/\_\_init\_\_.py                                 |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_edition/command.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_edition/context.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_edition/decider.py                                      |       30 |        0 |       12 |        0 |    100.0% |           |
| src/cora/data/features/register\_edition/handler.py                                      |       41 |        0 |        6 |        0 |    100.0% |           |
| src/cora/data/features/register\_edition/route.py                                        |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/register\_edition/tool.py                                         |       21 |        1 |        0 |        0 |     95.2% |       108 |
| src/cora/data/features/remove\_dataset\_from\_edition/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/remove\_dataset\_from\_edition/command.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/remove\_dataset\_from\_edition/decider.py                         |       14 |        0 |        8 |        0 |    100.0% |           |
| src/cora/data/features/remove\_dataset\_from\_edition/handler.py                         |       33 |        0 |        4 |        0 |    100.0% |           |
| src/cora/data/features/remove\_dataset\_from\_edition/route.py                           |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/remove\_dataset\_from\_edition/tool.py                            |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/seal\_edition/\_\_init\_\_.py                                     |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/seal\_edition/command.py                                          |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/seal\_edition/context.py                                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/seal\_edition/decider.py                                          |       27 |        0 |       14 |        0 |    100.0% |           |
| src/cora/data/features/seal\_edition/handler.py                                          |      101 |        8 |       38 |        7 |     89.2% |104, 107, 164, 166, 184, 236, 252, 275 |
| src/cora/data/features/seal\_edition/route.py                                            |       21 |        1 |        0 |        0 |     95.2% |       124 |
| src/cora/data/features/seal\_edition/tool.py                                             |       19 |        1 |        0 |        0 |     94.7% |        78 |
| src/cora/data/features/withdraw\_edition/\_\_init\_\_.py                                 |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/withdraw\_edition/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/withdraw\_edition/context.py                                      |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/features/withdraw\_edition/decider.py                                      |       12 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/features/withdraw\_edition/handler.py                                      |       44 |        1 |        8 |        1 |     96.2% |       118 |
| src/cora/data/features/withdraw\_edition/route.py                                        |       17 |        1 |        0 |        0 |     94.1% |        92 |
| src/cora/data/features/withdraw\_edition/tool.py                                         |       19 |        1 |        0 |        0 |     94.7% |        58 |
| src/cora/data/ports/\_\_init\_\_.py                                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/ports/checksum\_computer.py                                                |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/ports/checksum\_verifier.py                                                |       42 |        3 |        0 |        0 |     92.9% |204, 213-214 |
| src/cora/data/ports/distribution\_lookup.py                                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/ports/edition\_serializer.py                                               |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/ports/scan\_reader.py                                                      |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/projections/\_\_init\_\_.py                                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/projections/acquisition\_summary.py                                        |       18 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/projections/attestation\_summary.py                                        |       26 |        0 |        2 |        0 |    100.0% |           |
| src/cora/data/projections/distribution\_summary.py                                       |       77 |        4 |       22 |        2 |     93.9% |273, 276, 279-280 |
| src/cora/data/projections/edition\_summary.py                                            |       45 |        2 |       12 |        1 |     94.7% |   180-181 |
| src/cora/data/projections/summary.py                                                     |       23 |        0 |        4 |        0 |    100.0% |           |
| src/cora/data/routes.py                                                                  |       72 |        2 |       16 |        0 |     97.7% |   257-258 |
| src/cora/data/tools.py                                                                   |       40 |        0 |        0 |        0 |    100.0% |           |
| src/cora/data/wire.py                                                                    |       73 |        2 |       10 |        1 |     96.4% |217-218, 277-\>288 |
| src/cora/decision/\_\_init\_\_.py                                                        |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/\_bootstrap.py                                                         |        2 |        2 |        0 |        0 |      0.0% |      8-10 |
| src/cora/decision/\_projections.py                                                       |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/adapters/\_\_init\_\_.py                                               |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/adapters/postgres\_model\_usage\_lookup.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/adapters/postgres\_spend\_lookup.py                                    |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/aggregates/\_\_init\_\_.py                                             |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/aggregates/decision/\_\_init\_\_.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/aggregates/decision/entries.py                                         |       35 |        0 |        2 |        0 |    100.0% |           |
| src/cora/decision/aggregates/decision/events.py                                          |       54 |        0 |       14 |        0 |    100.0% |           |
| src/cora/decision/aggregates/decision/evolver.py                                         |       34 |        0 |       14 |        0 |    100.0% |           |
| src/cora/decision/aggregates/decision/read.py                                            |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/aggregates/decision/state.py                                           |      247 |        0 |       44 |        0 |    100.0% |           |
| src/cora/decision/catalog.py                                                             |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/errors.py                                                              |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/\_\_init\_\_.py                                               |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/append\_inferences/\_\_init\_\_.py                            |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/append\_inferences/command.py                                 |       29 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/append\_inferences/handler.py                                 |       58 |        0 |       10 |        0 |    100.0% |           |
| src/cora/decision/features/append\_inferences/route.py                                   |       43 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/append\_inferences/tool.py                                    |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/get\_decision/\_\_init\_\_.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/get\_decision/handler.py                                      |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/decision/features/get\_decision/query.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/get\_decision/route.py                                        |       20 |        0 |        2 |        0 |    100.0% |           |
| src/cora/decision/features/get\_decision/tool.py                                         |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/decision/features/list\_decisions/\_\_init\_\_.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/list\_decisions/handler.py                                    |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/list\_decisions/query.py                                      |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/list\_decisions/route.py                                      |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/list\_decisions/tool.py                                       |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/rate\_decision/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/rate\_decision/command.py                                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/rate\_decision/decider.py                                     |        9 |        0 |        2 |        0 |    100.0% |           |
| src/cora/decision/features/rate\_decision/handler.py                                     |       34 |        0 |        4 |        0 |    100.0% |           |
| src/cora/decision/features/rate\_decision/route.py                                       |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/rate\_decision/tool.py                                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/register\_decision/\_\_init\_\_.py                            |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/register\_decision/command.py                                 |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/register\_decision/context.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/register\_decision/decider.py                                 |       25 |        0 |        8 |        0 |    100.0% |           |
| src/cora/decision/features/register\_decision/handler.py                                 |       42 |        0 |        8 |        0 |    100.0% |           |
| src/cora/decision/features/register\_decision/route.py                                   |       31 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/features/register\_decision/tool.py                                    |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/projections/\_\_init\_\_.py                                            |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/projections/ratings.py                                                 |       20 |        0 |        2 |        0 |    100.0% |           |
| src/cora/decision/projections/summary.py                                                 |       18 |        0 |        2 |        0 |    100.0% |           |
| src/cora/decision/routes.py                                                              |       37 |        2 |        8 |        0 |     95.6% |   105-106 |
| src/cora/decision/tools.py                                                               |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/decision/wire.py                                                                |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/\_\_init\_\_.py                                                       |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/\_enclosure\_seed.py                                                  |       46 |        0 |        8 |        0 |    100.0% |           |
| src/cora/enclosure/\_monitor.py                                                          |       98 |        1 |       22 |        0 |     99.2% |       201 |
| src/cora/enclosure/\_projections.py                                                      |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/adapters/\_\_init\_\_.py                                              |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/adapters/postgres\_enclosure\_lookup.py                               |       36 |        0 |        8 |        0 |    100.0% |           |
| src/cora/enclosure/aggregates/\_\_init\_\_.py                                            |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/aggregates/\_value\_types.py                                          |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/enclosure/aggregates/enclosure/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/aggregates/enclosure/events.py                                        |       55 |        2 |       16 |        1 |     95.8% |     83-88 |
| src/cora/enclosure/aggregates/enclosure/evolver.py                                       |       22 |        0 |        6 |        0 |    100.0% |           |
| src/cora/enclosure/aggregates/enclosure/permit\_probes.py                                |       25 |        1 |        2 |        1 |     92.6% |        81 |
| src/cora/enclosure/aggregates/enclosure/state.py                                         |       50 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/errors.py                                                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/\_\_init\_\_.py                                              |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/decommission\_enclosure/\_\_init\_\_.py                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/decommission\_enclosure/command.py                           |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/decommission\_enclosure/decider.py                           |       13 |        0 |        4 |        0 |    100.0% |           |
| src/cora/enclosure/features/decommission\_enclosure/handler.py                           |       33 |        2 |        2 |        1 |     91.4% |    98-107 |
| src/cora/enclosure/features/decommission\_enclosure/route.py                             |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/decommission\_enclosure/tool.py                              |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/observe\_enclosure\_status/\_\_init\_\_.py                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/observe\_enclosure\_status/command.py                        |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/observe\_enclosure\_status/decider.py                        |       18 |        0 |        8 |        0 |    100.0% |           |
| src/cora/enclosure/features/observe\_enclosure\_status/handler.py                        |       36 |        4 |        4 |        2 |     85.0% |105-114, 133-141 |
| src/cora/enclosure/features/observe\_enclosure\_status/route.py                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/observe\_enclosure\_status/tool.py                           |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/register\_enclosure/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/register\_enclosure/command.py                               |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/register\_enclosure/decider.py                               |       13 |        0 |        4 |        0 |    100.0% |           |
| src/cora/enclosure/features/register\_enclosure/handler.py                               |       34 |        2 |        2 |        1 |     91.7% |   118-126 |
| src/cora/enclosure/features/register\_enclosure/route.py                                 |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/features/register\_enclosure/tool.py                                  |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/ports/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/ports/enclosure\_observer.py                                          |       19 |        0 |        2 |        0 |    100.0% |           |
| src/cora/enclosure/projections/\_\_init\_\_.py                                           |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/projections/enclosure.py                                              |       42 |        0 |       10 |        0 |    100.0% |           |
| src/cora/enclosure/routes.py                                                             |       35 |        0 |        8 |        0 |    100.0% |           |
| src/cora/enclosure/tools.py                                                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/enclosure/wire.py                                                               |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_\_init\_\_.py                                                       |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_asset\_update\_handler.py                                           |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_\_init\_\_.py                                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_alternate\_identifier\_body.py                             |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_asset\_owner\_body.py                                      |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_asset\_persistent\_identifier\_body.py                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_drawing\_body.py                                           |        6 |        1 |        0 |        0 |     83.3% |        48 |
| src/cora/equipment/\_bodies/\_fixture\_persistent\_identifier\_body.py                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_placement\_body.py                                         |        8 |        1 |        0 |        0 |     87.5% |        91 |
| src/cora/equipment/\_bodies/\_sub\_assembly\_link\_body.py                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_template\_slot\_body.py                                    |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bodies/\_template\_wire\_body.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_bootstrap.py                                                        |       46 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/\_frame\_update\_handler.py                                           |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_mount\_update\_handler.py                                           |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_pidinst/\_\_init\_\_.py                                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_pidinst/\_response.py                                               |       57 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/\_pidinst/\_serializer.py                                             |       87 |        1 |       36 |        3 |     96.7% |175-\>177, 218, 383-\>385 |
| src/cora/equipment/\_pidinst/\_types.py                                                  |       96 |        3 |       24 |        3 |     95.0% |442, 509, 517 |
| src/cora/equipment/\_projections.py                                                      |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/adapters/\_\_init\_\_.py                                              |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/adapters/postgres\_assembly\_lookup.py                                |       17 |        6 |        2 |        0 |     57.9% | 34-38, 42 |
| src/cora/equipment/adapters/postgres\_asset\_lookup.py                                   |       29 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/adapters/postgres\_family\_lookup.py                                  |       17 |        6 |        2 |        0 |     57.9% | 33-37, 41 |
| src/cora/equipment/adapters/postgres\_role\_lookup.py                                    |       17 |        6 |        2 |        0 |     57.9% | 50-54, 58 |
| src/cora/equipment/aggregates/\_\_init\_\_.py                                            |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/\_drawing.py                                               |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/\_partition\_rule.py                                       |      177 |        0 |       62 |        3 |     98.7% |541-\>exit, 646-\>exit, 692-\>exit |
| src/cora/equipment/aggregates/\_placement.py                                             |       33 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/\_value\_types.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/assembly/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/assembly/\_content\_hash.py                                |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/assembly/events.py                                         |       73 |        0 |       18 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/assembly/evolver.py                                        |       28 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/assembly/read.py                                           |       44 |        0 |       14 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/assembly/state.py                                          |      214 |        0 |       26 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/asset/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/asset/events.py                                            |      214 |        0 |      106 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/asset/evolver.py                                           |       83 |        0 |       46 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/asset/read.py                                              |       16 |        4 |        2 |        0 |     66.7% |     40-43 |
| src/cora/equipment/aggregates/asset/settings\_validation.py                              |       60 |        0 |       24 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/asset/state.py                                             |      294 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/\_\_init\_\_.py                                     |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/\_family\_registry.py                               |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/\_family\_seed\_registry.py                         |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/affordance.py                                       |       67 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/events.py                                           |       60 |        0 |       22 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/evolver.py                                          |       31 |        0 |       12 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/read.py                                             |       52 |        2 |       10 |        2 |     93.5% |  139, 233 |
| src/cora/equipment/aggregates/family/settings\_validation.py                             |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/family/state.py                                            |       65 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/fixture/\_\_init\_\_.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/fixture/events.py                                          |       45 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/fixture/evolver.py                                         |       21 |        1 |        8 |        1 |     93.1% |        53 |
| src/cora/equipment/aggregates/fixture/read.py                                            |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/fixture/state.py                                           |       31 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/frame/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/frame/events.py                                            |       48 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/frame/evolver.py                                           |       21 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/frame/read.py                                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/frame/state.py                                             |       57 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/model/\_\_init\_\_.py                                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/model/\_model\_registry.py                                 |       17 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/model/events.py                                            |       69 |        0 |       22 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/model/evolver.py                                           |       27 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/model/read.py                                              |       18 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/model/state.py                                             |      117 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/mount/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/mount/events.py                                            |       57 |        0 |       18 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/mount/evolver.py                                           |       27 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/mount/read.py                                              |       10 |        3 |        0 |        0 |     70.0% |     21-23 |
| src/cora/equipment/aggregates/mount/state.py                                             |       77 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/role/\_\_init\_\_.py                                       |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/role/\_role\_registry.py                                   |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/role/\_signal\_type.py                                     |       13 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/role/events.py                                             |       36 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/role/evolver.py                                            |       15 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/role/read.py                                               |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/aggregates/role/state.py                                              |       38 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/errors.py                                                             |       47 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/\_\_init\_\_.py                                              |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/activate\_asset/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/activate\_asset/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/activate\_asset/decider.py                                   |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/activate\_asset/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/activate\_asset/route.py                                     |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/activate\_asset/tool.py                                      |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_assembly\_presents\_as/\_\_init\_\_.py                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_assembly\_presents\_as/command.py                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_assembly\_presents\_as/decider.py                       |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_assembly\_presents\_as/handler.py                       |       35 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_assembly\_presents\_as/route.py                         |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_assembly\_presents\_as/tool.py                          |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_alternate\_identifier/\_\_init\_\_.py            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_alternate\_identifier/command.py                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_alternate\_identifier/decider.py                 |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_alternate\_identifier/handler.py                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_alternate\_identifier/route.py                   |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_alternate\_identifier/tool.py                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_family/\_\_init\_\_.py                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_family/command.py                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_family/decider.py                                |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_family/handler.py                                |       39 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_family/route.py                                  |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_family/tool.py                                   |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_owner/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_owner/command.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_owner/decider.py                                 |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_owner/handler.py                                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_owner/route.py                                   |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_owner/tool.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_port/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_port/command.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_port/decider.py                                  |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_port/handler.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_port/route.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_asset\_port/tool.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_family\_presents\_as/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_family\_presents\_as/command.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_family\_presents\_as/decider.py                         |       18 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_family\_presents\_as/handler.py                         |       35 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_family\_presents\_as/route.py                           |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_family\_presents\_as/tool.py                            |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_model\_family/\_\_init\_\_.py                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_model\_family/command.py                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_model\_family/decider.py                                |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_model\_family/handler.py                                |       36 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_model\_family/route.py                                  |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/add\_model\_family/tool.py                                   |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_asset\_persistent\_id/\_\_init\_\_.py                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_asset\_persistent\_id/command.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_asset\_persistent\_id/decider.py                     |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_asset\_persistent\_id/handler.py                     |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_asset\_persistent\_id/route.py                       |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_asset\_persistent\_id/tool.py                        |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_fixture\_persistent\_id/\_\_init\_\_.py              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_fixture\_persistent\_id/command.py                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_fixture\_persistent\_id/decider.py                   |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_fixture\_persistent\_id/handler.py                   |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_fixture\_persistent\_id/route.py                     |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/assign\_fixture\_persistent\_id/tool.py                      |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/attach\_asset\_to\_fixture/\_\_init\_\_.py                   |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/attach\_asset\_to\_fixture/command.py                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/attach\_asset\_to\_fixture/context.py                        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/attach\_asset\_to\_fixture/decider.py                        |       25 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/features/attach\_asset\_to\_fixture/handler.py                        |       37 |        2 |        2 |        1 |     92.3% |    99-107 |
| src/cora/equipment/features/attach\_asset\_to\_fixture/route.py                          |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/attach\_asset\_to\_fixture/tool.py                           |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/bind\_asset\_to\_facility/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/bind\_asset\_to\_facility/command.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/bind\_asset\_to\_facility/decider.py                         |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/bind\_asset\_to\_facility/handler.py                         |       34 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/bind\_asset\_to\_facility/route.py                           |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/bind\_asset\_to\_facility/tool.py                            |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_asset/\_\_init\_\_.py                          |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_asset/command.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_asset/context.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_asset/decider.py                               |       15 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_asset/handler.py                               |       36 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_asset/route.py                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_asset/tool.py                                  |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_frame/\_\_init\_\_.py                          |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_frame/command.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_frame/context.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_frame/decider.py                               |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_frame/handler.py                               |       34 |        2 |        2 |        1 |     91.7% |     87-96 |
| src/cora/equipment/features/decommission\_frame/route.py                                 |       16 |        3 |        0 |        0 |     81.2% | 42-43, 81 |
| src/cora/equipment/features/decommission\_frame/tool.py                                  |       16 |        2 |        0 |        0 |     87.5% |     48-49 |
| src/cora/equipment/features/decommission\_mount/\_\_init\_\_.py                          |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_mount/command.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_mount/context.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_mount/decider.py                               |       15 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/features/decommission\_mount/handler.py                               |       35 |        2 |        2 |        1 |     91.9% |     80-88 |
| src/cora/equipment/features/decommission\_mount/route.py                                 |       16 |        3 |        0 |        0 |     81.2% | 30-31, 63 |
| src/cora/equipment/features/decommission\_mount/tool.py                                  |       16 |        2 |        0 |        0 |     87.5% |     40-41 |
| src/cora/equipment/features/define\_assembly/\_\_init\_\_.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_assembly/command.py                                  |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_assembly/context.py                                  |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_assembly/decider.py                                  |       53 |        1 |       32 |        1 |     97.6% |       143 |
| src/cora/equipment/features/define\_assembly/handler.py                                  |       46 |        2 |        8 |        1 |     94.4% |   114-122 |
| src/cora/equipment/features/define\_assembly/route.py                                    |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_assembly/tool.py                                     |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_family/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_family/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_family/decider.py                                    |        9 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_family/handler.py                                    |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_family/route.py                                      |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_family/tool.py                                       |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_model/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_model/command.py                                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_model/decider.py                                     |       14 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_model/handler.py                                     |       39 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_model/route.py                                       |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_model/tool.py                                        |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_role/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_role/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_role/decider.py                                      |       17 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_role/handler.py                                      |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_role/route.py                                        |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/define\_role/tool.py                                         |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/degrade\_asset/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/degrade\_asset/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/degrade\_asset/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/degrade\_asset/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/degrade\_asset/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/degrade\_asset/tool.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_assembly/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_assembly/command.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_assembly/decider.py                               |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_assembly/handler.py                               |       31 |        2 |        2 |        1 |     90.9% |     75-84 |
| src/cora/equipment/features/deprecate\_assembly/route.py                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_assembly/tool.py                                  |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_family/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_family/command.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_family/decider.py                                 |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_family/handler.py                                 |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_family/route.py                                   |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_family/tool.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_model/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_model/command.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_model/decider.py                                  |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_model/handler.py                                  |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_model/route.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/deprecate\_model/tool.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/detach\_asset\_from\_fixture/\_\_init\_\_.py                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/detach\_asset\_from\_fixture/command.py                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/detach\_asset\_from\_fixture/decider.py                      |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/detach\_asset\_from\_fixture/handler.py                      |       31 |        2 |        2 |        1 |     90.9% |     78-86 |
| src/cora/equipment/features/detach\_asset\_from\_fixture/route.py                        |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/detach\_asset\_from\_fixture/tool.py                         |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/enter\_asset\_maintenance/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/enter\_asset\_maintenance/command.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/enter\_asset\_maintenance/decider.py                         |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/enter\_asset\_maintenance/handler.py                         |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/enter\_asset\_maintenance/route.py                           |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/enter\_asset\_maintenance/tool.py                            |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/exit\_asset\_maintenance/\_\_init\_\_.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/exit\_asset\_maintenance/command.py                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/exit\_asset\_maintenance/decider.py                          |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/exit\_asset\_maintenance/handler.py                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/exit\_asset\_maintenance/route.py                            |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/exit\_asset\_maintenance/tool.py                             |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/fault\_asset/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/fault\_asset/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/fault\_asset/decider.py                                      |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/fault\_asset/handler.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/fault\_asset/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/fault\_asset/tool.py                                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset/handler.py                                        |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset/query.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset/route.py                                          |       20 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset/tool.py                                           |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_integration\_view/\_\_init\_\_.py                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_integration\_view/handler.py                     |       50 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_integration\_view/query.py                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_integration\_view/route.py                       |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_integration\_view/tool.py                        |       24 |        1 |        2 |        1 |     92.3% |       113 |
| src/cora/equipment/features/get\_asset\_integration\_view/view.py                        |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_pidinst/\_\_init\_\_.py                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_pidinst/\_view\_assembler.py                     |       25 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_pidinst/handler.py                               |       32 |        2 |        2 |        1 |     91.2% |     85-93 |
| src/cora/equipment/features/get\_asset\_pidinst/query.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_asset\_pidinst/route.py                                 |       15 |        1 |        0 |        0 |     93.3% |        99 |
| src/cora/equipment/features/get\_asset\_pidinst/tool.py                                  |       22 |        3 |        0 |        0 |     86.4% |     92-99 |
| src/cora/equipment/features/get\_family/\_\_init\_\_.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_family/handler.py                                       |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_family/query.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_family/route.py                                         |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_family/tool.py                                          |       27 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture/\_\_init\_\_.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture/handler.py                                      |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture/query.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture/route.py                                        |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture/tool.py                                         |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture\_pidinst/\_\_init\_\_.py                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture\_pidinst/\_view\_assembler.py                   |       49 |        1 |       18 |        1 |     97.0% |       121 |
| src/cora/equipment/features/get\_fixture\_pidinst/handler.py                             |       27 |        2 |        4 |        1 |     90.3% |     76-84 |
| src/cora/equipment/features/get\_fixture\_pidinst/route.py                               |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_fixture\_pidinst/tool.py                                |       29 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_model/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_model/handler.py                                        |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_model/query.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_model/route.py                                          |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/get\_model/tool.py                                           |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/install\_asset/\_\_init\_\_.py                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/install\_asset/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/install\_asset/context.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/install\_asset/decider.py                                    |       22 |        0 |       14 |        0 |    100.0% |           |
| src/cora/equipment/features/install\_asset/handler.py                                    |       40 |        4 |        4 |        2 |     86.4% |74-81, 105-106 |
| src/cora/equipment/features/install\_asset/route.py                                      |       15 |        3 |        0 |        0 |     80.0% | 24-25, 65 |
| src/cora/equipment/features/install\_asset/tool.py                                       |       15 |        2 |        0 |        0 |     86.7% |     41-42 |
| src/cora/equipment/features/list\_assets/\_\_init\_\_.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_assets/handler.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_assets/query.py                                        |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_assets/route.py                                        |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_assets/tool.py                                         |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_families/\_\_init\_\_.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_families/handler.py                                    |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_families/query.py                                      |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_families/route.py                                      |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_families/tool.py                                       |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_fixtures/\_\_init\_\_.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_fixtures/handler.py                                    |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_fixtures/query.py                                      |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_fixtures/route.py                                      |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/list\_fixtures/tool.py                                       |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/mint\_missing\_asset\_persistent\_ids/\_\_init\_\_.py        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/mint\_missing\_asset\_persistent\_ids/command.py             |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/mint\_missing\_asset\_persistent\_ids/handler.py             |       55 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/features/mint\_missing\_asset\_persistent\_ids/route.py               |       28 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/mint\_missing\_asset\_persistent\_ids/tool.py                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_asset/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_asset/command.py                                   |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_asset/decider.py                                   |       24 |        0 |       12 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_asset/handler.py                                   |       42 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_asset/route.py                                     |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_asset/tool.py                                      |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_fixture/\_\_init\_\_.py                            |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_fixture/command.py                                 |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_fixture/context.py                                 |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_fixture/decider.py                                 |       86 |        3 |       54 |        3 |     95.7% |103, 109, 198 |
| src/cora/equipment/features/register\_fixture/handler.py                                 |       65 |        2 |        6 |        1 |     95.8% |   121-129 |
| src/cora/equipment/features/register\_fixture/route.py                                   |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_fixture/tool.py                                    |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_frame/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_frame/command.py                                   |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_frame/decider.py                                   |       23 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_frame/handler.py                                   |       31 |        2 |        2 |        1 |     90.9% |     91-99 |
| src/cora/equipment/features/register\_frame/route.py                                     |       20 |        5 |        0 |        0 |     75.0% |74-75, 128-140 |
| src/cora/equipment/features/register\_frame/tool.py                                      |       20 |        4 |        0 |        0 |     80.0% |     78-90 |
| src/cora/equipment/features/register\_mount/\_\_init\_\_.py                              |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_mount/command.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_mount/context.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_mount/decider.py                                   |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/register\_mount/handler.py                                   |       35 |        2 |        2 |        1 |     91.9% |    94-102 |
| src/cora/equipment/features/register\_mount/route.py                                     |       20 |        4 |        0 |        0 |     80.0% |68-69, 126-138 |
| src/cora/equipment/features/register\_mount/tool.py                                      |       19 |        3 |        0 |        0 |     84.2% |     60-72 |
| src/cora/equipment/features/relocate\_asset/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/relocate\_asset/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/relocate\_asset/decider.py                                   |       16 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/features/relocate\_asset/handler.py                                   |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/relocate\_asset/route.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/relocate\_asset/tool.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_assembly\_presents\_as/\_\_init\_\_.py               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_assembly\_presents\_as/command.py                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_assembly\_presents\_as/decider.py                    |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_assembly\_presents\_as/handler.py                    |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_assembly\_presents\_as/route.py                      |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_assembly\_presents\_as/tool.py                       |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_alternate\_identifier/\_\_init\_\_.py         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_alternate\_identifier/command.py              |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_alternate\_identifier/decider.py              |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_alternate\_identifier/handler.py              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_alternate\_identifier/route.py                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_alternate\_identifier/tool.py                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_family/\_\_init\_\_.py                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_family/command.py                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_family/decider.py                             |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_family/handler.py                             |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_family/route.py                               |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_family/tool.py                                |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_owner/\_\_init\_\_.py                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_owner/command.py                              |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_owner/decider.py                              |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_owner/handler.py                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_owner/route.py                                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_owner/tool.py                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_port/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_port/command.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_port/decider.py                               |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_port/handler.py                               |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_port/route.py                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_asset\_port/tool.py                                  |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_family\_presents\_as/\_\_init\_\_.py                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_family\_presents\_as/command.py                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_family\_presents\_as/decider.py                      |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_family\_presents\_as/handler.py                      |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_family\_presents\_as/route.py                        |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_family\_presents\_as/tool.py                         |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_model\_family/\_\_init\_\_.py                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_model\_family/command.py                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_model\_family/decider.py                             |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_model\_family/handler.py                             |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_model\_family/route.py                               |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/remove\_model\_family/tool.py                                |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/restore\_asset/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/restore\_asset/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/restore\_asset/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/restore\_asset/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/restore\_asset/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/restore\_asset/tool.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/uninstall\_asset/\_\_init\_\_.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/uninstall\_asset/command.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/uninstall\_asset/context.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/uninstall\_asset/decider.py                                  |       15 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/features/uninstall\_asset/handler.py                                  |       38 |        3 |        4 |        2 |     88.1% |98-106, 127 |
| src/cora/equipment/features/uninstall\_asset/route.py                                    |       16 |        3 |        0 |        0 |     81.2% | 30-31, 63 |
| src/cora/equipment/features/uninstall\_asset/tool.py                                     |       16 |        2 |        0 |        0 |     87.5% |     40-41 |
| src/cora/equipment/features/update\_asset\_partition\_rule/\_\_init\_\_.py               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_partition\_rule/command.py                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_partition\_rule/decider.py                    |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_partition\_rule/handler.py                    |       33 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_partition\_rule/route.py                      |       68 |        8 |       10 |        1 |     80.8% |   163-216 |
| src/cora/equipment/features/update\_asset\_partition\_rule/tool.py                       |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_settings/\_\_init\_\_.py                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_settings/command.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_settings/context.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_settings/decider.py                           |       14 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_settings/handler.py                           |       38 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_settings/route.py                             |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_asset\_settings/tool.py                              |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_family\_settings\_schema/\_\_init\_\_.py             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_family\_settings\_schema/command.py                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_family\_settings\_schema/decider.py                  |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_family\_settings\_schema/handler.py                  |       34 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_family\_settings\_schema/route.py                    |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_family\_settings\_schema/tool.py                     |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_frame\_placement/\_\_init\_\_.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_frame\_placement/command.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_frame\_placement/decider.py                          |       18 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_frame\_placement/handler.py                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_frame\_placement/route.py                            |       18 |        4 |        0 |        0 |     77.8% |53-54, 100-101 |
| src/cora/equipment/features/update\_frame\_placement/tool.py                             |       16 |        2 |        0 |        0 |     87.5% |     57-58 |
| src/cora/equipment/features/update\_mount\_placement/\_\_init\_\_.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_mount\_placement/command.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_mount\_placement/decider.py                          |       15 |        0 |        8 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_mount\_placement/handler.py                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/update\_mount\_placement/route.py                            |       17 |        3 |        0 |        0 |     82.4% | 29-30, 77 |
| src/cora/equipment/features/update\_mount\_placement/tool.py                             |       16 |        2 |        0 |        0 |     87.5% |     39-40 |
| src/cora/equipment/features/version\_assembly/\_\_init\_\_.py                            |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_assembly/command.py                                 |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_assembly/context.py                                 |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_assembly/decider.py                                 |       54 |        2 |       34 |        1 |     94.3% |   130-131 |
| src/cora/equipment/features/version\_assembly/handler.py                                 |       45 |        2 |        8 |        1 |     94.3% |   101-109 |
| src/cora/equipment/features/version\_assembly/route.py                                   |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_assembly/tool.py                                    |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_family/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_family/command.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_family/decider.py                                   |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_family/handler.py                                   |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_family/route.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_family/tool.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_model/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_model/command.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_model/decider.py                                    |       14 |        0 |        6 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_model/handler.py                                    |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_model/route.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/features/version\_model/tool.py                                       |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/ports/\_\_init\_\_.py                                                 |        1 |        1 |        0 |        0 |      0.0% |        10 |
| src/cora/equipment/projections/\_\_init\_\_.py                                           |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/projections/assembly\_summary.py                                      |       32 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/projections/asset.py                                                  |      100 |        7 |       40 |        5 |     91.4% |365, 371, 381-383, 394, 532 |
| src/cora/equipment/projections/asset\_family\_membership.py                              |       20 |        2 |        4 |        1 |     87.5% |     87-88 |
| src/cora/equipment/projections/asset\_location.py                                        |       23 |        2 |        6 |        1 |     89.7% |     94-95 |
| src/cora/equipment/projections/family.py                                                 |       32 |        0 |       12 |        0 |    100.0% |           |
| src/cora/equipment/projections/fixture\_summary.py                                       |       22 |        0 |        4 |        0 |    100.0% |           |
| src/cora/equipment/projections/frame\_children.py                                        |       20 |        4 |        6 |        1 |     73.1% |     66-72 |
| src/cora/equipment/projections/frame\_consumers.py                                       |       27 |        3 |       10 |        2 |     86.5% |106, 127-128 |
| src/cora/equipment/projections/frame\_summary.py                                         |       25 |        6 |        6 |        1 |     64.5% |     74-87 |
| src/cora/equipment/projections/model.py                                                  |       42 |        0 |       10 |        0 |    100.0% |           |
| src/cora/equipment/projections/mount\_children.py                                        |       21 |        2 |        6 |        1 |     88.9% |     84-85 |
| src/cora/equipment/projections/mount\_slot\_code.py                                      |       23 |        2 |        6 |        1 |     89.7% |     84-85 |
| src/cora/equipment/projections/mount\_summary.py                                         |       30 |        3 |       10 |        2 |     87.5% |96, 113-114 |
| src/cora/equipment/projections/role.py                                                   |       18 |        0 |        2 |        0 |    100.0% |           |
| src/cora/equipment/routes.py                                                             |      127 |        8 |       12 |        0 |     94.2% |357-358, 377-378, 394-395, 409-410 |
| src/cora/equipment/tools.py                                                              |      126 |        0 |        0 |        0 |    100.0% |           |
| src/cora/equipment/wire.py                                                               |       25 |        2 |        2 |        1 |     88.9% |  241, 262 |
| src/cora/federation/\_\_init\_\_.py                                                      |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/\_actor\_update\_handler.py                                          |       30 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/\_bootstrap.py                                                       |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/\_federation\_dtos.py                                                |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/\_projections.py                                                     |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/\_subscribers.py                                                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/adapters/\_\_init\_\_.py                                             |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/adapters/federation\_registry.py                                     |       39 |        3 |       14 |        3 |     88.7% |66, 73, 105 |
| src/cora/federation/adapters/in\_memory\_permit\_lookup.py                               |       29 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/adapters/in\_memory\_publish\_port.py                                |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/adapters/in\_memory\_pull\_port.py                                   |       42 |        0 |        6 |        0 |    100.0% |           |
| src/cora/federation/adapters/in\_memory\_signature\_port.py                              |       33 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/adapters/postgres\_credential\_lookup.py                             |       19 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/adapters/postgres\_facility\_lookup.py                               |       39 |        7 |        8 |        2 |     76.6% |100-104, 122, 124 |
| src/cora/federation/aggregates/\_\_init\_\_.py                                           |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/\_value\_types.py                                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/credential/\_\_init\_\_.py                                |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/credential/events.py                                      |       56 |        3 |       18 |        1 |     94.6% |   282-284 |
| src/cora/federation/aggregates/credential/evolver.py                                     |       29 |        0 |       10 |        0 |    100.0% |           |
| src/cora/federation/aggregates/credential/read.py                                        |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/aggregates/credential/state.py                                       |       47 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/facility/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/facility/\_stream\_id.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/facility/events.py                                        |       56 |        0 |       14 |        0 |    100.0% |           |
| src/cora/federation/aggregates/facility/evolver.py                                       |       25 |        0 |        8 |        0 |    100.0% |           |
| src/cora/federation/aggregates/facility/read.py                                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/facility/state.py                                         |       85 |        0 |        6 |        0 |    100.0% |           |
| src/cora/federation/aggregates/permit/\_\_init\_\_.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/permit/events.py                                          |       79 |       10 |       28 |        2 |     85.0% |105-118, 378-394 |
| src/cora/federation/aggregates/permit/evolver.py                                         |       32 |        3 |       12 |        1 |     90.9% |     76-78 |
| src/cora/federation/aggregates/permit/read.py                                            |       27 |        7 |        0 |        0 |     74.1% |63, 67, 71, 75, 95-97 |
| src/cora/federation/aggregates/permit/state.py                                           |       84 |        2 |        0 |        0 |     97.6% |   330-334 |
| src/cora/federation/aggregates/seal/\_\_init\_\_.py                                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/seal/\_key\_separation.py                                 |        5 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/aggregates/seal/\_stream\_id.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/aggregates/seal/events.py                                            |       51 |        3 |       18 |        1 |     94.2% |   297-299 |
| src/cora/federation/aggregates/seal/evolver.py                                           |       27 |        0 |       10 |        0 |    100.0% |           |
| src/cora/federation/aggregates/seal/read.py                                              |       22 |        5 |        2 |        0 |     70.8% |     88-92 |
| src/cora/federation/aggregates/seal/state.py                                             |       86 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/errors.py                                                            |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/\_\_init\_\_.py                                             |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/abort\_credential\_rotation/\_\_init\_\_.py                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/abort\_credential\_rotation/command.py                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/abort\_credential\_rotation/decider.py                      |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/abort\_credential\_rotation/handler.py                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/abort\_credential\_rotation/route.py                        |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/abort\_credential\_rotation/tool.py                         |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/activate\_permit/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/activate\_permit/command.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/activate\_permit/decider.py                                 |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/activate\_permit/handler.py                                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/activate\_permit/route.py                                   |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/activate\_permit/tool.py                                    |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/add\_facility\_trust\_anchor\_credential/\_\_init\_\_.py    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/add\_facility\_trust\_anchor\_credential/command.py         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/add\_facility\_trust\_anchor\_credential/decider.py         |       15 |        0 |        8 |        0 |    100.0% |           |
| src/cora/federation/features/add\_facility\_trust\_anchor\_credential/handler.py         |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/add\_facility\_trust\_anchor\_credential/route.py           |       17 |        3 |        0 |        0 |     82.4% | 50-51, 97 |
| src/cora/federation/features/add\_facility\_trust\_anchor\_credential/tool.py            |       18 |        3 |        0 |        0 |     83.3% |     57-67 |
| src/cora/federation/features/complete\_credential\_rotation/\_\_init\_\_.py              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_credential\_rotation/command.py                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_credential\_rotation/decider.py                   |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_credential\_rotation/handler.py                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_credential\_rotation/route.py                     |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_credential\_rotation/tool.py                      |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_seal\_republishing/\_\_init\_\_.py                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_seal\_republishing/command.py                     |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_seal\_republishing/decider.py                     |       26 |        0 |       12 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_seal\_republishing/handler.py                     |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_seal\_republishing/route.py                       |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/complete\_seal\_republishing/tool.py                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/decommission\_facility/\_\_init\_\_.py                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/decommission\_facility/command.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/decommission\_facility/decider.py                           |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/decommission\_facility/handler.py                           |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/decommission\_facility/route.py                             |       18 |        3 |        0 |        0 |     83.3% | 47-48, 86 |
| src/cora/federation/features/decommission\_facility/tool.py                              |       18 |        3 |        0 |        0 |     83.3% |     60-67 |
| src/cora/federation/features/define\_permit/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/define\_permit/command.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/define\_permit/decider.py                                   |       45 |        2 |       30 |        0 |     97.3% |   102-103 |
| src/cora/federation/features/define\_permit/handler.py                                   |       41 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/define\_permit/route.py                                     |       37 |        1 |        4 |        1 |     95.1% |       161 |
| src/cora/federation/features/define\_permit/tool.py                                      |       33 |        3 |        4 |        1 |     83.8% |     82-88 |
| src/cora/federation/features/get\_credential/\_\_init\_\_.py                             |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/get\_credential/handler.py                                  |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/federation/features/get\_credential/query.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/get\_credential/route.py                                    |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/get\_credential/tool.py                                     |       24 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/get\_permit/\_\_init\_\_.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/get\_permit/handler.py                                      |       53 |       22 |       14 |        1 |     50.7% |94-105, 109-110, 197-220 |
| src/cora/federation/features/get\_permit/query.py                                        |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/get\_permit/route.py                                        |       35 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/get\_permit/tool.py                                         |       35 |        1 |        2 |        1 |     94.6% |        99 |
| src/cora/federation/features/get\_seal/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/get\_seal/handler.py                                        |       34 |        1 |        6 |        1 |     95.0% |       131 |
| src/cora/federation/features/get\_seal/query.py                                          |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/get\_seal/route.py                                          |       24 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/get\_seal/tool.py                                           |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/initialize\_seal/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/initialize\_seal/command.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/initialize\_seal/decider.py                                 |       45 |        2 |       22 |        0 |     97.0% |   150-156 |
| src/cora/federation/features/initialize\_seal/handler.py                                 |       51 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/initialize\_seal/route.py                                   |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/initialize\_seal/tool.py                                    |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_credentials/\_\_init\_\_.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_credentials/handler.py                                |       22 |        1 |        0 |        0 |     95.5% |        78 |
| src/cora/federation/features/list\_credentials/query.py                                  |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_credentials/route.py                                  |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_credentials/tool.py                                   |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_permits/\_\_init\_\_.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_permits/handler.py                                    |       22 |        1 |        0 |        0 |     95.5% |        86 |
| src/cora/federation/features/list\_permits/query.py                                      |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_permits/route.py                                      |       28 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_permits/tool.py                                       |       28 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_seals/\_\_init\_\_.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_seals/handler.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_seals/query.py                                        |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_seals/route.py                                        |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/list\_seals/tool.py                                         |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/register\_credential/\_\_init\_\_.py                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/register\_credential/command.py                             |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/register\_credential/decider.py                             |       26 |        2 |       10 |        0 |     94.4% |     77-82 |
| src/cora/federation/features/register\_credential/handler.py                             |       41 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/register\_credential/route.py                               |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/register\_credential/tool.py                                |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/register\_facility/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/register\_facility/command.py                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/register\_facility/decider.py                               |       21 |        0 |       12 |        0 |    100.0% |           |
| src/cora/federation/features/register\_facility/handler.py                               |       44 |        2 |        4 |        0 |     95.8% |   186-191 |
| src/cora/federation/features/register\_facility/route.py                                 |       28 |        6 |        0 |        0 |     78.6% |61, 127-128, 184-199 |
| src/cora/federation/features/register\_facility/tool.py                                  |       20 |        3 |        0 |        0 |     85.0% |     83-95 |
| src/cora/federation/features/remove\_facility\_trust\_anchor\_credential/\_\_init\_\_.py |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/remove\_facility\_trust\_anchor\_credential/command.py      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/remove\_facility\_trust\_anchor\_credential/decider.py      |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/federation/features/remove\_facility\_trust\_anchor\_credential/handler.py      |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/remove\_facility\_trust\_anchor\_credential/route.py        |       18 |        3 |        0 |        0 |     83.3% | 52-53, 97 |
| src/cora/federation/features/remove\_facility\_trust\_anchor\_credential/tool.py         |       18 |        3 |        0 |        0 |     83.3% |     68-79 |
| src/cora/federation/features/resume\_permit/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/resume\_permit/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/resume\_permit/decider.py                                   |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/resume\_permit/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/resume\_permit/route.py                                     |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/resume\_permit/tool.py                                      |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_credential/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_credential/command.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_credential/decider.py                               |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_credential/handler.py                               |       40 |        0 |        2 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_credential/route.py                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_credential/tool.py                                  |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_permit/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_permit/command.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_permit/decider.py                                   |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_permit/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_permit/route.py                                     |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/revoke\_permit/tool.py                                      |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/rotate\_seal\_online\_key/\_\_init\_\_.py                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/rotate\_seal\_online\_key/command.py                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/rotate\_seal\_online\_key/decider.py                        |       33 |        0 |       16 |        0 |    100.0% |           |
| src/cora/federation/features/rotate\_seal\_online\_key/handler.py                        |       50 |        2 |        2 |        0 |     96.2% |   155-156 |
| src/cora/federation/features/rotate\_seal\_online\_key/route.py                          |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/rotate\_seal\_online\_key/tool.py                           |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/sign\_seal\_pointer/\_\_init\_\_.py                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/sign\_seal\_pointer/command.py                              |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/sign\_seal\_pointer/decider.py                              |       16 |        0 |        8 |        0 |    100.0% |           |
| src/cora/federation/features/sign\_seal\_pointer/handler.py                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/sign\_seal\_pointer/route.py                                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/sign\_seal\_pointer/tool.py                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_credential\_rotation/\_\_init\_\_.py                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_credential\_rotation/command.py                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_credential\_rotation/decider.py                      |       19 |        0 |       10 |        0 |    100.0% |           |
| src/cora/federation/features/start\_credential\_rotation/handler.py                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_credential\_rotation/route.py                        |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_credential\_rotation/tool.py                         |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_seal\_republishing/\_\_init\_\_.py                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_seal\_republishing/command.py                        |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_seal\_republishing/decider.py                        |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/start\_seal\_republishing/handler.py                        |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_seal\_republishing/route.py                          |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/start\_seal\_republishing/tool.py                           |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/suspend\_permit/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/suspend\_permit/command.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/suspend\_permit/decider.py                                  |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/federation/features/suspend\_permit/handler.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/suspend\_permit/route.py                                    |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/features/suspend\_permit/tool.py                                     |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/projections/\_\_init\_\_.py                                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/projections/credential.py                                            |       39 |        7 |       10 |        3 |     79.6% |155-160, 163-168, 179 |
| src/cora/federation/projections/facility.py                                              |       33 |        1 |        8 |        1 |     95.1% |       181 |
| src/cora/federation/projections/permit.py                                                |       48 |       21 |       14 |        2 |     46.8% |111-125, 179-215 |
| src/cora/federation/projections/seal.py                                                  |       39 |        5 |       10 |        1 |     83.7% |   159-169 |
| src/cora/federation/routes.py                                                            |       71 |        2 |       10 |        0 |     97.5% |   162-163 |
| src/cora/federation/tools.py                                                             |       56 |        0 |        0 |        0 |    100.0% |           |
| src/cora/federation/wire.py                                                              |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/\_\_init\_\_.py                                                  |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/\_\_init\_\_.py                                         |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/canonicalization\_registry.py                           |       36 |        0 |       18 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/default\_canonicalization\_adapter.py                   |       30 |        4 |        2 |        0 |     87.5% |50-51, 66-67 |
| src/cora/infrastructure/adapters/default\_signing\_adapter.py                            |       57 |        3 |        8 |        1 |     93.8% |131-132, 157 |
| src/cora/infrastructure/adapters/in\_memory\_assembly\_lookup.py                         |       15 |        4 |        0 |        0 |     73.3% |37-38, 46-47 |
| src/cora/infrastructure/adapters/in\_memory\_asset\_lookup.py                            |       41 |        0 |       14 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_clearance\_template\_lookup.py              |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_credential\_lookup.py                       |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_enclosure\_lookup.py                        |       28 |        0 |        6 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_event\_store.py                             |       61 |        0 |       18 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_facility\_lookup.py                         |       28 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_family\_lookup.py                           |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_idempotency\_store.py                       |       67 |        2 |       18 |        2 |     95.3% |  121, 138 |
| src/cora/infrastructure/adapters/in\_memory\_profile\_store.py                           |       20 |        1 |        2 |        0 |     95.5% |        57 |
| src/cora/infrastructure/adapters/in\_memory\_role\_lookup.py                             |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/in\_memory\_secret\_store.py                            |       19 |       19 |        0 |        0 |      0.0% |     15-43 |
| src/cora/infrastructure/adapters/in\_memory\_signer.py                                   |       30 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/adapters/introspection\_token\_verifier.py                       |      126 |        7 |       44 |        5 |     92.9% |257-258, 277-\>279, 333, 338, 352, 354-355 |
| src/cora/infrastructure/adapters/jwt\_token\_verifier.py                                 |       79 |        6 |       16 |        0 |     93.7% |171, 196-199, 247 |
| src/cora/infrastructure/adapters/postgres\_event\_store.py                               |       72 |        4 |       26 |        5 |     90.8% |122, 192, 236, 243-\>238, 250 |
| src/cora/infrastructure/adapters/postgres\_idempotency\_store.py                         |       40 |        2 |       12 |        2 |     92.3% |  127, 153 |
| src/cora/infrastructure/adapters/postgres\_profile\_store.py                             |       36 |        5 |        4 |        0 |     82.5% |    99-103 |
| src/cora/infrastructure/adapters/signing\_registry.py                                    |       28 |        1 |       14 |        1 |     95.2% |        70 |
| src/cora/infrastructure/adapters/stub\_persistent\_identifier\_minter.py                 |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/auth/\_\_init\_\_.py                                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/auth/\_routed\_path.py                                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/auth/bearer\_auth\_middleware.py                                 |       66 |        4 |       14 |        1 |     93.8% |270-286, 325 |
| src/cora/infrastructure/auth/build\_idp\_registry.py                                     |       23 |        2 |       12 |        1 |     91.4% |   103-108 |
| src/cora/infrastructure/auth/config.py                                                   |       56 |        0 |       12 |        0 |    100.0% |           |
| src/cora/infrastructure/auth/exception\_handlers.py                                      |       44 |        0 |        6 |        0 |    100.0% |           |
| src/cora/infrastructure/auth/idp\_registry.py                                            |       48 |        0 |       18 |        0 |    100.0% |           |
| src/cora/infrastructure/capture\_scan\_ingestor\_binding.py                              |       77 |        0 |       20 |        0 |    100.0% |           |
| src/cora/infrastructure/config.py                                                        |      380 |       11 |       72 |        6 |     96.2% |908, 1751-1755, 1838-1842, 1850-1854, 1863-1867, 1986-1991 |
| src/cora/infrastructure/control\_port\_route.py                                          |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/deps.py                                                          |      129 |        1 |       18 |        2 |     98.0% |1235, 1426-\>1422 |
| src/cora/infrastructure/edge\_runtime.py                                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/event\_envelope.py                                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/event\_payload.py                                                |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/evolver.py                                                       |        6 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/idempotency.py                                                   |       98 |        1 |       38 |        1 |     98.5% |115, 332-\>exit |
| src/cora/infrastructure/idempotency\_pruner.py                                           |       34 |        1 |        4 |        0 |     97.4% |        95 |
| src/cora/infrastructure/kernel.py                                                        |       36 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/list\_query.py                                                   |       94 |        0 |       30 |        0 |    100.0% |           |
| src/cora/infrastructure/logging.py                                                       |       26 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/mcp\_principal.py                                                |       39 |        1 |       12 |        1 |     96.1% |       147 |
| src/cora/infrastructure/observability/\_\_init\_\_.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/observability/correlation.py                                     |        9 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/observability/decorator.py                                       |       18 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/observability/gen\_ai.py                                         |       81 |        0 |       14 |        0 |    100.0% |           |
| src/cora/infrastructure/observability/gpu\_accounting.py                                 |       96 |        3 |       34 |        2 |     96.2% |74-75, 151 |
| src/cora/infrastructure/observability/log\_processor.py                                  |       15 |        0 |        4 |        1 |     94.7% |   41-\>43 |
| src/cora/infrastructure/observability/provider.py                                        |       49 |        7 |       12 |        2 |     82.0% |171-191, 208 |
| src/cora/infrastructure/observability/surface\_context.py                                |       18 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/\_\_init\_\_.py                                            |       35 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/allocation\_lookup.py                                      |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/assembly\_lookup.py                                        |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/asset\_lookup.py                                           |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/authorize.py                                               |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/beam\_availability\_lookup.py                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/byte\_signer.py                                            |       39 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/canonicalizer.py                                           |       27 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/capability\_lookup.py                                      |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/caution\_lookup.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/clearance\_lookup.py                                       |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/clearance\_template\_lookup.py                             |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/clock.py                                                   |       29 |        2 |        0 |        0 |     93.1% |    38, 81 |
| src/cora/infrastructure/ports/compute\_reachability\_lookup.py                           |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/consequence\_lookup.py                                     |       13 |        2 |        0 |        0 |     84.6% |     72-73 |
| src/cora/infrastructure/ports/credential\_lookup.py                                      |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/dataset\_distribution\_lookup.py                           |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/enclosure\_lookup.py                                       |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/event\_publisher.py                                        |        4 |        4 |        0 |        0 |      0.0% |     51-57 |
| src/cora/infrastructure/ports/event\_store.py                                            |       34 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/facility\_lookup.py                                        |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/family\_lookup.py                                          |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/federation/\_\_init\_\_.py                                 |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/federation/errors.py                                       |       72 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/federation/permit\_lookup.py                               |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/federation/publish\_port.py                                |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/federation/pull\_port.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/federation/signature\_port.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/federation/value\_types.py                                 |       71 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/id\_generator.py                                           |       16 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/idempotency\_store.py                                      |       41 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/inference\_recorder.py                                     |       30 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/language\_model\_lookup.py                                 |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/llm.py                                                     |       66 |        0 |        4 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/logbook\_mirror.py                                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/model\_usage\_lookup.py                                    |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/principal\_liveness\_lookup.py                             |       13 |        2 |        0 |        0 |     84.6% |     96-97 |
| src/cora/infrastructure/ports/profile\_store.py                                          |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/role\_lookup.py                                            |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/run\_actor\_involvement\_lookup.py                         |        9 |        2 |        0 |        0 |     77.8% |     56-57 |
| src/cora/infrastructure/ports/secret\_store.py                                           |       15 |       15 |        0 |        0 |      0.0% |    58-136 |
| src/cora/infrastructure/ports/signer.py                                                  |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/ports/spend\_guard.py                                            |        9 |        1 |        0 |        0 |     88.9% |        79 |
| src/cora/infrastructure/ports/spend\_lookup.py                                           |       17 |        1 |        0 |        0 |     94.1% |       167 |
| src/cora/infrastructure/ports/supply\_lookup.py                                          |       53 |       11 |        2 |        1 |     78.2% |176-178, 224-225, 228-229, 258-259, 294-295, 300 |
| src/cora/infrastructure/ports/token\_verifier.py                                         |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/postgres/\_\_init\_\_.py                                         |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/postgres/pool.py                                                 |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/projection/\_\_init\_\_.py                                       |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/projection/bookmark.py                                           |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/infrastructure/projection/cursor.py                                             |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/projection/drain.py                                              |       34 |        1 |        8 |        1 |     95.2% |       120 |
| src/cora/infrastructure/projection/handler.py                                            |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/projection/lifespan.py                                           |       30 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/projection/registry.py                                           |       30 |        0 |        4 |        0 |    100.0% |           |
| src/cora/infrastructure/projection/wakeup.py                                             |       53 |        0 |       12 |        2 |     96.9% |132-\>134, 160-\>164 |
| src/cora/infrastructure/projection/worker.py                                             |       59 |        6 |        8 |        0 |     91.0% |   208-228 |
| src/cora/infrastructure/published\_artifact/\_\_init\_\_.py                              |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/published\_artifact/\_stages.py                                  |       64 |        3 |       28 |        0 |     96.7% |87-88, 238 |
| src/cora/infrastructure/published\_artifact/orchestrator.py                              |       48 |        1 |       16 |        1 |     96.9% |       135 |
| src/cora/infrastructure/read\_only\_event\_store.py                                      |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_\_init\_\_.py                                   |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_bundle.py                                       |       63 |        4 |       20 |        3 |     91.6% |146-147, 228-229, 239-\>243 |
| src/cora/infrastructure/record\_export/\_dispositions.py                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_export.py                                       |       53 |        0 |       12 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_hashing.py                                      |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_leaf\_rule.py                                   |       39 |        1 |       22 |        3 |     93.4% |94-\>86, 105-\>107, 112 |
| src/cora/infrastructure/record\_export/\_manifest.py                                     |       92 |        0 |       18 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_redact\_tier1.py                                |       88 |        7 |       42 |        4 |     90.0% |90-93, 103, 110, 122 |
| src/cora/infrastructure/record\_export/\_redact\_tier2.py                                |       40 |        0 |       20 |        2 |     96.7% |405-\>392, 413-\>392 |
| src/cora/infrastructure/record\_export/\_redaction.py                                    |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_registry.py                                     |       31 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_render.py                                       |       22 |        0 |       10 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_shell.py                                        |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_stream\_types.py                                |        8 |        0 |        2 |        0 |    100.0% |           |
| src/cora/infrastructure/record\_export/\_tokens.py                                       |       14 |        0 |        4 |        0 |    100.0% |           |
| src/cora/infrastructure/routing.py                                                       |       46 |        1 |       12 |        1 |     96.6% |       169 |
| src/cora/infrastructure/schema\_version.py                                               |       60 |        0 |        8 |        0 |    100.0% |           |
| src/cora/infrastructure/signing.py                                                       |       56 |        1 |       12 |        1 |     97.1% |       119 |
| src/cora/infrastructure/update\_handler.py                                               |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/\_\_init\_\_.py                                                       |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/\_advise\_wire.py                                                     |       33 |        1 |        2 |        1 |     94.3% |       136 |
| src/cora/operation/\_bootstrap.py                                                        |        2 |        2 |        0 |        0 |      0.0% |     11-13 |
| src/cora/operation/\_conduct\_preparation.py                                             |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/\_conduct\_wire.py                                                    |       39 |        0 |        6 |        0 |    100.0% |           |
| src/cora/operation/\_control\_dispatch\_context.py                                       |       19 |        2 |        0 |        0 |     89.5% |    74, 79 |
| src/cora/operation/\_partition\_rule\_eval.py                                            |       47 |        2 |       16 |        3 |     92.1% |73, 241-\>240, 246 |
| src/cora/operation/\_procedure\_update\_handler.py                                       |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/\_projections.py                                                      |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/\_pseudoaxis/\_\_init\_\_.py                                          |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/\_pseudoaxis/\_evaluator.py                                           |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/\_pseudoaxis/\_expander.py                                            |       26 |        3 |        2 |        1 |     85.7% |120, 123-124 |
| src/cora/operation/\_recipe\_expansion/\_\_init\_\_.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/\_recipe\_expansion/\_expand.py                                       |       54 |        5 |       28 |        2 |     89.0% |96-101, 163 |
| src/cora/operation/\_recipe\_expansion/\_replay.py                                       |       29 |        0 |        8 |        0 |    100.0% |           |
| src/cora/operation/\_recipe\_expansion/\_resolved\_steps\_replay.py                      |        7 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/\_steering\_resume.py                                                 |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/acquisitions.py                                                       |      147 |        1 |       42 |        3 |     97.9% |366, 593-\>598, 595-\>598 |
| src/cora/operation/adapters/\_\_init\_\_.py                                              |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/adapters/\_llm\_decide\_prompt.py                                     |       32 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/adapters/\_optional\_tango.py                                         |        7 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/adapters/\_optional\_torch.py                                         |       10 |        2 |        4 |        2 |     71.4% |    28, 34 |
| src/cora/operation/adapters/\_tree\_hash.py                                              |       45 |        0 |       14 |        0 |    100.0% |           |
| src/cora/operation/adapters/botorch\_decide\_port.py                                     |      100 |        1 |       26 |        2 |     97.6% |301, 321-\>320 |
| src/cora/operation/adapters/caproto\_control\_port.py                                    |      115 |        3 |       30 |        3 |     95.9% |173, 224-\>227, 258-\>260, 284-285 |
| src/cora/operation/adapters/compute\_port\_config.py                                     |       22 |        0 |        6 |        0 |    100.0% |           |
| src/cora/operation/adapters/control\_port\_beam\_availability\_lookup.py                 |       50 |        2 |       16 |        2 |     93.9% |  116, 128 |
| src/cora/operation/adapters/control\_port\_config.py                                     |       45 |        0 |       18 |        0 |    100.0% |           |
| src/cora/operation/adapters/control\_port\_registry.py                                   |       55 |        1 |       16 |        2 |     95.8% |113-\>exit, 240 |
| src/cora/operation/adapters/decide\_port\_config.py                                      |       43 |        0 |       12 |        0 |    100.0% |           |
| src/cora/operation/adapters/decider\_replayability.py                                    |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/adapters/epics\_ca\_control\_port.py                                  |       98 |        2 |       24 |        2 |     96.7% |  405, 448 |
| src/cora/operation/adapters/epics\_pva\_control\_port.py                                 |      142 |       19 |       52 |       10 |     82.0% |194, 209, 213-\>218, 216-217, 221, 226-233, 237, 241, 326-327, 444, 446, 465-\>exit |
| src/cora/operation/adapters/fdt\_transfer\_port.py                                       |       67 |        6 |       16 |        0 |     90.4% |71-72, 86, 89-91 |
| src/cora/operation/adapters/globus\_compute\_port.py                                     |       57 |        0 |        8 |        0 |    100.0% |           |
| src/cora/operation/adapters/globus\_transfer\_port.py                                    |       61 |        0 |       12 |        0 |    100.0% |           |
| src/cora/operation/adapters/grid\_walk\_decide\_port.py                                  |       37 |        0 |       14 |        0 |    100.0% |           |
| src/cora/operation/adapters/in\_memory\_compute\_port.py                                 |       44 |        0 |        6 |        0 |    100.0% |           |
| src/cora/operation/adapters/in\_memory\_control\_port.py                                 |       59 |        2 |       12 |        2 |     94.4% |  171, 242 |
| src/cora/operation/adapters/in\_memory\_decide\_port.py                                  |       16 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/adapters/in\_memory\_recipe\_expander.py                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/adapters/in\_memory\_transfer\_port.py                                |       50 |        1 |       10 |        1 |     96.7% |       127 |
| src/cora/operation/adapters/llm\_decide\_port.py                                         |       71 |        0 |       12 |        0 |    100.0% |           |
| src/cora/operation/adapters/local\_process\_compute\_port.py                             |       93 |       12 |       26 |        5 |     85.7% |162-163, 190, 197, 216-217, 267-270, 277, 294 |
| src/cora/operation/adapters/postgres\_procedure\_activity\_lookup.py                     |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/adapters/postgres\_procedure\_outcome\_lookup.py                      |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/adapters/read\_only\_control\_port.py                                 |       32 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/adapters/sobol\_decide\_port.py                                       |       40 |        0 |       10 |        0 |    100.0% |           |
| src/cora/operation/adapters/staged\_decide\_port.py                                      |       25 |        0 |        6 |        0 |    100.0% |           |
| src/cora/operation/adapters/tango\_control\_port.py                                      |      138 |        9 |       42 |        4 |     92.8% |335, 342, 349, 536-539, 548, 551 |
| src/cora/operation/aggregates/\_\_init\_\_.py                                            |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/aggregates/procedure/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/aggregates/procedure/entries.py                                       |       70 |        2 |       12 |        2 |     95.1% |  291, 427 |
| src/cora/operation/aggregates/procedure/events.py                                        |      137 |        0 |       54 |        0 |    100.0% |           |
| src/cora/operation/aggregates/procedure/evolver.py                                       |       53 |        0 |       28 |        0 |    100.0% |           |
| src/cora/operation/aggregates/procedure/read.py                                          |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/aggregates/procedure/state.py                                         |      293 |        0 |       16 |        0 |    100.0% |           |
| src/cora/operation/conductor.py                                                          |      798 |       26 |      192 |        2 |     97.2% |989-990, 1504, 1543, 1706-1709, 1939-1942, 2178-2181, 2357, 2550, 2579-2582, 2700-2703 |
| src/cora/operation/errors.py                                                             |       62 |       14 |        0 |        0 |     77.4% |92-93, 141-146, 212-220, 240-246 |
| src/cora/operation/features/\_\_init\_\_.py                                              |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/abort\_procedure/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/abort\_procedure/command.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/abort\_procedure/decider.py                                  |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/abort\_procedure/handler.py                                  |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/abort\_procedure/route.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/abort\_procedure/tool.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_activities/\_\_init\_\_.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_activities/command.py                                |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_activities/handler.py                                |       63 |        3 |       12 |        0 |     96.0% |   216-223 |
| src/cora/operation/features/append\_activities/route.py                                  |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_activities/tool.py                                   |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_diagnostics/\_\_init\_\_.py                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_diagnostics/command.py                               |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_diagnostics/handler.py                               |       60 |        5 |        8 |        1 |     91.2% |115-123, 169-176 |
| src/cora/operation/features/append\_diagnostics/route.py                                 |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_diagnostics/tool.py                                  |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_outcomes/\_\_init\_\_.py                             |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_outcomes/command.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_outcomes/handler.py                                  |       60 |        5 |        8 |        1 |     91.2% |114-122, 168-175 |
| src/cora/operation/features/append\_outcomes/route.py                                    |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/append\_outcomes/tool.py                                     |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/complete\_procedure/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/complete\_procedure/command.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/complete\_procedure/decider.py                               |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/complete\_procedure/handler.py                               |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/complete\_procedure/route.py                                 |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/complete\_procedure/tool.py                                  |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_from\_procedure/\_\_init\_\_.py                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_from\_procedure/command.py                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_from\_procedure/handler.py                          |       38 |        0 |       10 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_from\_procedure/route.py                            |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_from\_procedure/tool.py                             |       21 |        2 |        0 |        0 |     90.5% |     82-83 |
| src/cora/operation/features/conduct\_or\_hold\_procedure/\_\_init\_\_.py                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_or\_hold\_procedure/command.py                      |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_or\_hold\_procedure/handler.py                      |       30 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_or\_hold\_procedure/route.py                        |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_or\_hold\_procedure/tool.py                         |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_procedure/\_\_init\_\_.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_procedure/command.py                                |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_procedure/handler.py                                |       30 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_procedure/route.py                                  |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_procedure/tool.py                                   |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_advised/\_\_init\_\_.py                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_advised/command.py                           |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_advised/handler.py                           |       40 |        2 |        4 |        1 |     93.2% |   121-129 |
| src/cora/operation/features/conduct\_until\_advised/route.py                             |       28 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_advised/tool.py                              |       20 |        2 |        0 |        0 |     90.0% |     71-72 |
| src/cora/operation/features/conduct\_until\_advised\_from/\_\_init\_\_.py                |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_advised\_from/command.py                     |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_advised\_from/handler.py                     |       49 |        3 |        8 |        1 |     93.0% |176, 215-220 |
| src/cora/operation/features/conduct\_until\_advised\_from/route.py                       |       28 |        2 |        0 |        0 |     92.9% |  110, 186 |
| src/cora/operation/features/conduct\_until\_advised\_from/tool.py                        |       20 |        2 |        0 |        0 |     90.0% |     72-73 |
| src/cora/operation/features/conduct\_until\_converged/\_\_init\_\_.py                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_converged/command.py                         |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_converged/handler.py                         |       31 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_converged/route.py                           |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/conduct\_until\_converged/tool.py                            |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/end\_iteration/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/end\_iteration/command.py                                    |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/end\_iteration/decider.py                                    |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/end\_iteration/handler.py                                    |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/end\_iteration/route.py                                      |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/end\_iteration/tool.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/get\_procedure/\_\_init\_\_.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/get\_procedure/handler.py                                    |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/features/get\_procedure/query.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/get\_procedure/route.py                                      |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/features/get\_procedure/tool.py                                       |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/features/hold\_procedure/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/hold\_procedure/command.py                                   |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/hold\_procedure/decider.py                                   |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/hold\_procedure/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/hold\_procedure/route.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/hold\_procedure/tool.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedure\_iterations/\_\_init\_\_.py                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedure\_iterations/handler.py                       |       37 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedure\_iterations/query.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedure\_iterations/route.py                         |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedure\_iterations/tool.py                          |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedures/\_\_init\_\_.py                             |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedures/handler.py                                  |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedures/query.py                                    |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedures/route.py                                    |       27 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/list\_procedures/tool.py                                     |       27 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure/command.py                               |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure/decider.py                               |       20 |        0 |       10 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure/handler.py                               |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure/route.py                                 |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure/tool.py                                  |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure\_from\_recipe/\_\_init\_\_.py            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure\_from\_recipe/command.py                 |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure\_from\_recipe/decider.py                 |       35 |        0 |       10 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure\_from\_recipe/handler.py                 |       49 |        0 |       12 |        1 |     98.4% | 147-\>155 |
| src/cora/operation/features/register\_procedure\_from\_recipe/route.py                   |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/register\_procedure\_from\_recipe/tool.py                    |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/resume\_procedure/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/resume\_procedure/command.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/resume\_procedure/decider.py                                 |       13 |        0 |        8 |        0 |    100.0% |           |
| src/cora/operation/features/resume\_procedure/handler.py                                 |       39 |        0 |        8 |        0 |    100.0% |           |
| src/cora/operation/features/resume\_procedure/route.py                                   |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/resume\_procedure/tool.py                                    |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_iteration/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_iteration/command.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_iteration/decider.py                                  |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/operation/features/start\_iteration/handler.py                                  |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_iteration/route.py                                    |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_iteration/tool.py                                     |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_procedure/\_\_init\_\_.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_procedure/command.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_procedure/context.py                                  |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_procedure/decider.py                                  |       33 |        0 |       22 |        0 |    100.0% |           |
| src/cora/operation/features/start\_procedure/handler.py                                  |       70 |        7 |       20 |        5 |     86.7% |220, 223, 226, 229, 231-235 |
| src/cora/operation/features/start\_procedure/route.py                                    |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/start\_procedure/tool.py                                     |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/truncate\_procedure/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/truncate\_procedure/command.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/truncate\_procedure/decider.py                               |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/operation/features/truncate\_procedure/handler.py                               |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/truncate\_procedure/route.py                                 |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/features/truncate\_procedure/tool.py                                  |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/\_\_init\_\_.py                                                 |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/compute\_port.py                                                |       80 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/control\_address.py                                             |       50 |        0 |       10 |        0 |    100.0% |           |
| src/cora/operation/ports/control\_port.py                                                |       54 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/decide\_port.py                                                 |       91 |        2 |       12 |        0 |     98.1% |   280-281 |
| src/cora/operation/ports/measurement.py                                                  |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/procedure\_activity\_lookup.py                                  |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/procedure\_outcome\_lookup.py                                   |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/recipe\_expander.py                                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/ports/transfer\_port.py                                               |       70 |        8 |        0 |        0 |     88.6% |254-256, 269-271, 283-284 |
| src/cora/operation/projections/\_\_init\_\_.py                                           |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/projections/procedure.py                                              |       54 |        0 |       18 |        0 |    100.0% |           |
| src/cora/operation/projections/procedure\_iterations.py                                  |       20 |        0 |        4 |        0 |    100.0% |           |
| src/cora/operation/routes.py                                                             |       68 |        4 |       12 |        0 |     95.0% |158-159, 233-234 |
| src/cora/operation/tools.py                                                              |       48 |        0 |        0 |        0 |    100.0% |           |
| src/cora/operation/wire.py                                                               |       47 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/\_\_init\_\_.py                                                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/\_bootstrap.py                                                           |        2 |        2 |        0 |        0 |      0.0% |     14-16 |
| src/cora/recipe/\_method\_update\_handler.py                                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/\_plan\_update\_handler.py                                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/\_practice\_update\_handler.py                                           |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/\_projections.py                                                         |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/\_role\_requirement\_body.py                                             |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/adapters/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/adapters/postgres\_capability\_lookup.py                                 |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/\_\_init\_\_.py                                               |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/capability/\_\_init\_\_.py                                    |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/capability/events.py                                          |       60 |        0 |       14 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/capability/evolver.py                                         |       24 |        0 |        8 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/capability/executor\_shape.py                                 |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/capability/parameters\_schema\_validation.py                  |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/capability/read.py                                            |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/capability/state.py                                           |      101 |        0 |       14 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/\_\_init\_\_.py                                        |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/events.py                                              |       81 |        0 |       30 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/evolver.py                                             |       39 |        0 |       14 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/execution\_pattern.py                                  |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/launch\_argv.py                                        |       22 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/launch\_spec.py                                        |       63 |        2 |       26 |        2 |     95.5% |  128, 149 |
| src/cora/recipe/aggregates/method/parameters\_validation.py                              |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/read.py                                                |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/method/state.py                                               |      180 |        0 |       12 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/\_\_init\_\_.py                                          |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/events.py                                                |       74 |        0 |       32 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/evolver.py                                               |       42 |        0 |       16 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/parameters\_validation.py                                |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/read.py                                                  |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/state.py                                                 |      226 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/wires\_reading.py                                        |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/plan/wires\_validation.py                                     |       57 |        1 |       34 |        2 |     96.7% |109-\>108, 236 |
| src/cora/recipe/aggregates/practice/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/practice/events.py                                            |       36 |        0 |       10 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/practice/evolver.py                                           |       21 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/practice/read.py                                              |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/practice/state.py                                             |       43 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/recipe/\_\_init\_\_.py                                        |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/recipe/body.py                                                |      133 |        4 |       48 |        3 |     95.0% |315, 325-327, 356-\>358 |
| src/cora/recipe/aggregates/recipe/events.py                                              |       43 |        0 |       10 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/recipe/evolver.py                                             |       21 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/recipe/read.py                                                |       33 |        5 |       10 |        0 |     83.7% |   126-130 |
| src/cora/recipe/aggregates/recipe/state.py                                               |       56 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/aggregates/recipe/steps\_validation.py                                   |       30 |        0 |       10 |        0 |    100.0% |           |
| src/cora/recipe/errors.py                                                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/\_\_init\_\_.py                                                 |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_method\_required\_role/\_\_init\_\_.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_method\_required\_role/command.py                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_method\_required\_role/decider.py                          |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_method\_required\_role/handler.py                          |       23 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_method\_required\_role/route.py                            |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_method\_required\_role/tool.py                             |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_plan\_wire/\_\_init\_\_.py                                 |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_plan\_wire/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_plan\_wire/context.py                                      |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_plan\_wire/decider.py                                      |       31 |        0 |       22 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_plan\_wire/handler.py                                      |       50 |        0 |       14 |        1 |     98.4% | 176-\>179 |
| src/cora/recipe/features/add\_plan\_wire/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/add\_plan\_wire/tool.py                                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/bind\_plan\_role/\_\_init\_\_.py                                |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/bind\_plan\_role/command.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/bind\_plan\_role/context.py                                     |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/bind\_plan\_role/decider.py                                     |       67 |        0 |       54 |        1 |     99.2% | 262-\>261 |
| src/cora/recipe/features/bind\_plan\_role/handler.py                                     |       69 |        4 |       22 |        4 |     89.0% |137-\>142, 140, 154-\>160, 187-189 |
| src/cora/recipe/features/bind\_plan\_role/route.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/bind\_plan\_role/tool.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_capability/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_capability/command.py                                   |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_capability/decider.py                                   |       15 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_capability/handler.py                                   |       31 |        2 |        2 |        1 |     90.9% |     82-90 |
| src/cora/recipe/features/define\_capability/route.py                                     |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_capability/tool.py                                      |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_method/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_method/command.py                                       |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_method/decider.py                                       |       25 |        0 |       12 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_method/handler.py                                       |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_method/route.py                                         |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_method/tool.py                                          |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_plan/\_\_init\_\_.py                                    |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_plan/command.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_plan/context.py                                         |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_plan/decider.py                                         |       32 |        0 |       16 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_plan/handler.py                                         |       62 |        0 |       18 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_plan/route.py                                           |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_plan/tool.py                                            |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_practice/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_practice/command.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_practice/decider.py                                     |        9 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_practice/handler.py                                     |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_practice/route.py                                       |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_practice/tool.py                                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_recipe/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_recipe/command.py                                       |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_recipe/decider.py                                       |       10 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_recipe/handler.py                                       |       38 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_recipe/route.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/define\_recipe/tool.py                                          |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_capability/\_\_init\_\_.py                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_capability/command.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_capability/decider.py                                |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_capability/handler.py                                |       31 |        2 |        2 |        1 |     90.9% |     74-83 |
| src/cora/recipe/features/deprecate\_capability/route.py                                  |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_capability/tool.py                                   |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_method/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_method/command.py                                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_method/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_method/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_method/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_method/tool.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_plan/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_plan/command.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_plan/decider.py                                      |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_plan/handler.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_plan/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_plan/tool.py                                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_practice/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_practice/command.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_practice/decider.py                                  |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_practice/handler.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_practice/route.py                                    |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_practice/tool.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_recipe/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_recipe/command.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_recipe/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_recipe/handler.py                                    |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_recipe/route.py                                      |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/deprecate\_recipe/tool.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_capability/\_\_init\_\_.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_capability/handler.py                                      |       32 |        2 |        6 |        1 |     92.1% |     82-90 |
| src/cora/recipe/features/get\_capability/query.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_capability/route.py                                        |       26 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_capability/tool.py                                         |       28 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_method/\_\_init\_\_.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_method/handler.py                                          |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_method/query.py                                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_method/route.py                                            |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_method/tool.py                                             |       27 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_plan/\_\_init\_\_.py                                       |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_plan/handler.py                                            |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_plan/query.py                                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_plan/route.py                                              |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_plan/tool.py                                               |       27 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_practice/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_practice/handler.py                                        |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_practice/query.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_practice/route.py                                          |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_practice/tool.py                                           |       27 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_recipe/\_\_init\_\_.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_recipe/handler.py                                          |       32 |        1 |        6 |        1 |     94.7% |       105 |
| src/cora/recipe/features/get\_recipe/query.py                                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_recipe/route.py                                            |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/get\_recipe/tool.py                                             |       27 |        2 |        2 |        1 |     89.7% |     65-66 |
| src/cora/recipe/features/inspect\_plan\_binding/\_\_init\_\_.py                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/inspect\_plan\_binding/handler.py                               |       70 |        0 |       28 |        0 |    100.0% |           |
| src/cora/recipe/features/inspect\_plan\_binding/query.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/inspect\_plan\_binding/route.py                                 |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/inspect\_plan\_binding/tool.py                                  |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/inspect\_plan\_binding/view.py                                  |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_methods/\_\_init\_\_.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_methods/handler.py                                        |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_methods/query.py                                          |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_methods/route.py                                          |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_methods/tool.py                                           |       23 |        3 |        0 |        0 |     87.0% |     72-79 |
| src/cora/recipe/features/list\_plans/\_\_init\_\_.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_plans/handler.py                                          |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_plans/query.py                                            |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_plans/route.py                                            |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_plans/tool.py                                             |       23 |        3 |        0 |        0 |     87.0% |     79-86 |
| src/cora/recipe/features/list\_practices/\_\_init\_\_.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_practices/handler.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_practices/query.py                                        |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_practices/route.py                                        |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/list\_practices/tool.py                                         |       22 |        3 |        0 |        0 |     86.4% |     72-79 |
| src/cora/recipe/features/remove\_method\_required\_role/\_\_init\_\_.py                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_method\_required\_role/command.py                       |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_method\_required\_role/decider.py                       |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_method\_required\_role/handler.py                       |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_method\_required\_role/route.py                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_method\_required\_role/tool.py                          |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_plan\_wire/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_plan\_wire/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_plan\_wire/decider.py                                   |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_plan\_wire/handler.py                                   |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_plan\_wire/route.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/remove\_plan\_wire/tool.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/unbind\_plan\_role/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/unbind\_plan\_role/command.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/unbind\_plan\_role/decider.py                                   |       11 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/unbind\_plan\_role/handler.py                                   |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/unbind\_plan\_role/route.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/unbind\_plan\_role/tool.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_capability\_suggested\_roles/\_\_init\_\_.py            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_capability\_suggested\_roles/command.py                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_capability\_suggested\_roles/decider.py                 |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_capability\_suggested\_roles/handler.py                 |       37 |        2 |        6 |        1 |     93.0% |     89-98 |
| src/cora/recipe/features/update\_capability\_suggested\_roles/route.py                   |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_capability\_suggested\_roles/tool.py                    |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_launch\_spec/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_launch\_spec/command.py                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_launch\_spec/decider.py                         |       23 |        0 |       16 |        1 |     97.4% |   58-\>60 |
| src/cora/recipe/features/update\_method\_launch\_spec/handler.py                         |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_launch\_spec/route.py                           |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_launch\_spec/tool.py                            |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_parameters\_schema/\_\_init\_\_.py              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_parameters\_schema/command.py                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_parameters\_schema/decider.py                   |       31 |        1 |       22 |        3 |     92.5% |90, 132-\>136, 133-\>132 |
| src/cora/recipe/features/update\_method\_parameters\_schema/handler.py                   |       37 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_parameters\_schema/route.py                     |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_method\_parameters\_schema/tool.py                      |       15 |        2 |        0 |        0 |     86.7% |     50-51 |
| src/cora/recipe/features/update\_plan\_default\_parameters/\_\_init\_\_.py               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_plan\_default\_parameters/command.py                    |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_plan\_default\_parameters/context.py                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_plan\_default\_parameters/decider.py                    |       13 |        0 |        4 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_plan\_default\_parameters/handler.py                    |       42 |        0 |        8 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_plan\_default\_parameters/route.py                      |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/update\_plan\_default\_parameters/tool.py                       |       15 |        2 |        0 |        0 |     86.7% |     50-51 |
| src/cora/recipe/features/version\_capability/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_capability/command.py                                  |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_capability/decider.py                                  |       16 |        0 |        8 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_capability/handler.py                                  |       31 |        2 |        2 |        1 |     90.9% |     75-85 |
| src/cora/recipe/features/version\_capability/route.py                                    |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_capability/tool.py                                     |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_method/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_method/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_method/decider.py                                      |       16 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_method/handler.py                                      |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_method/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_method/tool.py                                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_plan/\_\_init\_\_.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_plan/command.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_plan/decider.py                                        |       16 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_plan/handler.py                                        |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_plan/route.py                                          |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_plan/tool.py                                           |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_practice/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_practice/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_practice/decider.py                                    |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_practice/handler.py                                    |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_practice/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_practice/tool.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_recipe/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_recipe/command.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_recipe/decider.py                                      |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_recipe/handler.py                                      |       40 |        1 |        6 |        1 |     95.7% |       118 |
| src/cora/recipe/features/version\_recipe/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/features/version\_recipe/tool.py                                         |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/projections/\_\_init\_\_.py                                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/projections/capability.py                                                |       25 |        0 |        8 |        0 |    100.0% |           |
| src/cora/recipe/projections/method.py                                                    |       34 |        1 |       14 |        1 |     95.8% |       219 |
| src/cora/recipe/projections/plan.py                                                      |       30 |        0 |       10 |        0 |    100.0% |           |
| src/cora/recipe/projections/practice.py                                                  |       21 |        0 |        6 |        0 |    100.0% |           |
| src/cora/recipe/projections/recipe.py                                                    |       31 |       18 |       10 |        0 |     31.7% |67-73, 93-122 |
| src/cora/recipe/routes.py                                                                |       74 |        0 |       10 |        0 |    100.0% |           |
| src/cora/recipe/tools.py                                                                 |       72 |        0 |        0 |        0 |    100.0% |           |
| src/cora/recipe/wire.py                                                                  |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/\_\_init\_\_.py                                                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/\_bootstrap.py                                                              |        2 |        2 |        0 |        0 |      0.0% |     11-13 |
| src/cora/run/\_projections.py                                                            |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/\_run\_update\_handler.py                                                   |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/adapters/\_\_init\_\_.py                                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/adapters/postgres\_run\_actor\_involvement\_lookup.py                       |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/adapters/postgres\_run\_channel\_lookup.py                                  |       33 |        0 |        4 |        0 |    100.0% |           |
| src/cora/run/adapters/sim\_observation\_feeder.py                                        |       37 |        0 |        2 |        1 |     97.4% |  97-\>116 |
| src/cora/run/aggregates/\_\_init\_\_.py                                                  |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/\_\_init\_\_.py                                              |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/capture\_path.py                                             |       57 |        0 |        6 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/capture\_probes.py                                           |       26 |        1 |        2 |        1 |     92.9% |       167 |
| src/cora/run/aggregates/run/entries.py                                                   |       28 |        1 |        4 |        1 |     93.8% |       162 |
| src/cora/run/aggregates/run/events.py                                                    |      187 |        0 |       58 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/evolver.py                                                   |       52 |        0 |       26 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/experiment\_identity.py                                      |       35 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/feed\_heartbeats.py                                          |       26 |        1 |        4 |        1 |     93.3% |        66 |
| src/cora/run/aggregates/run/hold\_claims.py                                              |       33 |        7 |       10 |        2 |     74.4% |105, 107-112, 130-131, 139 |
| src/cora/run/aggregates/run/parameters\_validation.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/read.py                                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/safety\_envelope.py                                          |       16 |        0 |        6 |        0 |    100.0% |           |
| src/cora/run/aggregates/run/state.py                                                     |      321 |        0 |        8 |        1 |     99.7% |1974-\>1973 |
| src/cora/run/errors.py                                                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/\_\_init\_\_.py                                                    |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/abort\_run/\_\_init\_\_.py                                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/abort\_run/command.py                                              |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/abort\_run/decider.py                                              |       13 |        0 |        4 |        0 |    100.0% |           |
| src/cora/run/features/abort\_run/handler.py                                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/abort\_run/route.py                                                |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/abort\_run/tool.py                                                 |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/adjust\_run/\_\_init\_\_.py                                        |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/adjust\_run/command.py                                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/adjust\_run/context.py                                             |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/adjust\_run/decider.py                                             |       23 |        0 |        8 |        0 |    100.0% |           |
| src/cora/run/features/adjust\_run/handler.py                                             |       49 |        0 |       10 |        0 |    100.0% |           |
| src/cora/run/features/adjust\_run/route.py                                               |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/adjust\_run/tool.py                                                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/append\_observations/\_\_init\_\_.py                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/append\_observations/command.py                                    |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/append\_observations/handler.py                                    |       69 |        0 |       16 |        0 |    100.0% |           |
| src/cora/run/features/append\_observations/route.py                                      |       34 |        0 |        2 |        0 |    100.0% |           |
| src/cora/run/features/append\_observations/tool.py                                       |       20 |        0 |        2 |        0 |    100.0% |           |
| src/cora/run/features/complete\_run/\_\_init\_\_.py                                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/complete\_run/command.py                                           |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/complete\_run/decider.py                                           |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/run/features/complete\_run/handler.py                                           |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/complete\_run/route.py                                             |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/complete\_run/tool.py                                              |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/get\_run/\_\_init\_\_.py                                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/get\_run/handler.py                                                |       37 |        0 |        6 |        0 |    100.0% |           |
| src/cora/run/features/get\_run/query.py                                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/get\_run/route.py                                                  |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/run/features/get\_run/tool.py                                                   |       35 |        0 |        2 |        0 |    100.0% |           |
| src/cora/run/features/hold\_run/\_\_init\_\_.py                                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/hold\_run/command.py                                               |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/hold\_run/decider.py                                               |       14 |        0 |        8 |        0 |    100.0% |           |
| src/cora/run/features/hold\_run/handler.py                                               |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/hold\_run/route.py                                                 |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/hold\_run/tool.py                                                  |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/list\_runs/\_\_init\_\_.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/list\_runs/handler.py                                              |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/list\_runs/query.py                                                |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/list\_runs/route.py                                                |       25 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/list\_runs/tool.py                                                 |       26 |        3 |        0 |        0 |     88.5% |   100-113 |
| src/cora/run/features/record\_witnessed\_run/\_\_init\_\_.py                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run/command.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run/context.py                                  |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run/decider.py                                  |       41 |        1 |       16 |        1 |     96.5% |       172 |
| src/cora/run/features/record\_witnessed\_run/handler.py                                  |       70 |       11 |       18 |        7 |     77.3% |91-100, 104, 108, 112, 118, 123-125, 163-166 |
| src/cora/run/features/record\_witnessed\_run/route.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run/tool.py                                     |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run\_outcome/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run\_outcome/command.py                         |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run\_outcome/decider.py                         |       24 |        0 |       16 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run\_outcome/handler.py                         |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run\_outcome/route.py                           |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/record\_witnessed\_run\_outcome/tool.py                            |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/resume\_run/\_\_init\_\_.py                                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/resume\_run/command.py                                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/resume\_run/decider.py                                             |       26 |        1 |       16 |        1 |     95.2% |        76 |
| src/cora/run/features/resume\_run/handler.py                                             |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/resume\_run/route.py                                               |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/resume\_run/tool.py                                                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/start\_run/\_\_init\_\_.py                                         |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/start\_run/command.py                                              |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/start\_run/context.py                                              |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/start\_run/decider.py                                              |       53 |        1 |       26 |        1 |     97.5% |       315 |
| src/cora/run/features/start\_run/handler.py                                              |       94 |        2 |       28 |        0 |     98.4% |   385-388 |
| src/cora/run/features/start\_run/route.py                                                |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/start\_run/tool.py                                                 |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/stop\_run/\_\_init\_\_.py                                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/stop\_run/command.py                                               |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/stop\_run/decider.py                                               |       14 |        0 |        6 |        0 |    100.0% |           |
| src/cora/run/features/stop\_run/handler.py                                               |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/run/features/stop\_run/route.py                                                 |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/stop\_run/tool.py                                                  |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/truncate\_run/\_\_init\_\_.py                                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/truncate\_run/command.py                                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/truncate\_run/decider.py                                           |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/run/features/truncate\_run/handler.py                                           |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/truncate\_run/route.py                                             |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/features/truncate\_run/tool.py                                              |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/ports/\_\_init\_\_.py                                                       |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/ports/capture\_observer.py                                                  |       31 |        1 |        2 |        1 |     93.9% |       439 |
| src/cora/run/ports/run\_channel\_lookup.py                                               |       60 |        0 |        6 |        0 |    100.0% |           |
| src/cora/run/projections/\_\_init\_\_.py                                                 |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/projections/actor\_involvement.py                                           |       20 |        0 |        6 |        0 |    100.0% |           |
| src/cora/run/projections/summary.py                                                      |       66 |        0 |       18 |        1 |     98.8% | 113-\>112 |
| src/cora/run/routes.py                                                                   |       49 |        0 |        8 |        0 |    100.0% |           |
| src/cora/run/tools.py                                                                    |       30 |        0 |        0 |        0 |    100.0% |           |
| src/cora/run/wire.py                                                                     |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/\_\_init\_\_.py                                                          |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/\_bootstrap.py                                                           |        2 |        2 |        0 |        0 |      0.0% |     14-16 |
| src/cora/safety/\_clearance\_dtos.py                                                     |       45 |        1 |       14 |        1 |     96.6% |       193 |
| src/cora/safety/\_clearance\_template\_seed.py                                           |       39 |        0 |        6 |        0 |    100.0% |           |
| src/cora/safety/\_clearance\_template\_update\_handler.py                                |        6 |        6 |        0 |        0 |      0.0% |     38-75 |
| src/cora/safety/\_clearance\_update\_handler.py                                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/\_projections.py                                                         |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/adapters/\_\_init\_\_.py                                                 |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/adapters/postgres\_clearance\_lookup.py                                  |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/adapters/postgres\_clearance\_template\_lookup.py                        |       19 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/aggregates/\_\_init\_\_.py                                               |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance/\_\_init\_\_.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance/events.py                                           |      145 |        0 |       66 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance/evolver.py                                          |       48 |        0 |       18 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance/hazard\_classification.py                           |       76 |        0 |       20 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance/read.py                                             |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance/state.py                                            |      182 |        0 |       10 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance\_template/\_\_init\_\_.py                           |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance\_template/\_stream\_id.py                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance\_template/\_value\_types.py                         |       36 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance\_template/events.py                                 |       51 |        1 |       18 |        1 |     97.1% |       237 |
| src/cora/safety/aggregates/clearance\_template/evolver.py                                |       38 |       10 |       18 |        4 |     71.4% |68-69, 75-78, 85-86, 90-91 |
| src/cora/safety/aggregates/clearance\_template/read.py                                   |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/aggregates/clearance\_template/state.py                                  |       61 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/errors.py                                                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance/command.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance/decider.py                                  |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance/handler.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance/route.py                                    |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance/tool.py                                     |       17 |        3 |        0 |        0 |     82.4% |     38-45 |
| src/cora/safety/features/activate\_clearance\_template/\_\_init\_\_.py                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance\_template/command.py                        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance\_template/decider.py                        |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance\_template/handler.py                        |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance\_template/route.py                          |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/activate\_clearance\_template/tool.py                           |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/amend\_clearance/\_\_init\_\_.py                                |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/amend\_clearance/command.py                                     |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/amend\_clearance/context.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/amend\_clearance/decider.py                                     |       44 |        5 |       20 |        3 |     84.4% |117, 137-140, 150-\>149 |
| src/cora/safety/features/amend\_clearance/handler.py                                     |       44 |        2 |        4 |        1 |     93.8% |   113-122 |
| src/cora/safety/features/amend\_clearance/route.py                                       |       29 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/amend\_clearance/tool.py                                        |       26 |        5 |        0 |        0 |     80.8% |   125-149 |
| src/cora/safety/features/append\_clearance\_review\_step/\_\_init\_\_.py                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/append\_clearance\_review\_step/command.py                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/append\_clearance\_review\_step/decider.py                      |       26 |        0 |       14 |        0 |    100.0% |           |
| src/cora/safety/features/append\_clearance\_review\_step/handler.py                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/append\_clearance\_review\_step/route.py                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/append\_clearance\_review\_step/tool.py                         |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/approve\_clearance/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/approve\_clearance/command.py                                   |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/approve\_clearance/decider.py                                   |       13 |        0 |        8 |        0 |    100.0% |           |
| src/cora/safety/features/approve\_clearance/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/approve\_clearance/route.py                                     |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/approve\_clearance/tool.py                                      |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/define\_clearance\_template/\_\_init\_\_.py                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/define\_clearance\_template/command.py                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/define\_clearance\_template/decider.py                          |       16 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/define\_clearance\_template/handler.py                          |       36 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/define\_clearance\_template/route.py                            |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/define\_clearance\_template/tool.py                             |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/deprecate\_clearance\_template/\_\_init\_\_.py                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/deprecate\_clearance\_template/command.py                       |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/deprecate\_clearance\_template/decider.py                       |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/deprecate\_clearance\_template/handler.py                       |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/deprecate\_clearance\_template/route.py                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/deprecate\_clearance\_template/tool.py                          |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/expire\_clearance/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/expire\_clearance/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/expire\_clearance/decider.py                                    |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/expire\_clearance/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/expire\_clearance/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/expire\_clearance/tool.py                                       |       18 |        3 |        0 |        0 |     83.3% |     48-58 |
| src/cora/safety/features/get\_clearance/\_\_init\_\_.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance/handler.py                                       |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance/query.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance/route.py                                         |       34 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance/tool.py                                          |       36 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance\_template/\_\_init\_\_.py                        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance\_template/handler.py                             |       26 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance\_template/query.py                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance\_template/route.py                               |       20 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/get\_clearance\_template/tool.py                                |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearance\_templates/\_\_init\_\_.py                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearance\_templates/handler.py                           |       22 |        1 |        0 |        0 |     95.5% |        71 |
| src/cora/safety/features/list\_clearance\_templates/query.py                             |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearance\_templates/route.py                             |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearance\_templates/tool.py                              |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearances/\_\_init\_\_.py                                |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearances/handler.py                                     |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearances/query.py                                       |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearances/route.py                                       |       37 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/list\_clearances/tool.py                                        |       37 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/register\_clearance/\_\_init\_\_.py                             |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/register\_clearance/command.py                                  |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/register\_clearance/decider.py                                  |       36 |        0 |       20 |        0 |    100.0% |           |
| src/cora/safety/features/register\_clearance/handler.py                                  |       34 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/register\_clearance/route.py                                    |       29 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/register\_clearance/tool.py                                     |       60 |        9 |       14 |        1 |     78.4% |146, 151-165, 173 |
| src/cora/safety/features/reject\_clearance/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/reject\_clearance/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/reject\_clearance/decider.py                                    |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/reject\_clearance/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/reject\_clearance/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/reject\_clearance/tool.py                                       |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/start\_clearance\_review/\_\_init\_\_.py                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/start\_clearance\_review/command.py                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/start\_clearance\_review/decider.py                             |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/start\_clearance\_review/handler.py                             |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/start\_clearance\_review/route.py                               |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/start\_clearance\_review/tool.py                                |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/submit\_clearance/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/submit\_clearance/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/submit\_clearance/decider.py                                    |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/submit\_clearance/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/submit\_clearance/route.py                                      |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/submit\_clearance/tool.py                                       |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/version\_clearance\_template/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/version\_clearance\_template/command.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/version\_clearance\_template/decider.py                         |       20 |        0 |       12 |        0 |    100.0% |           |
| src/cora/safety/features/version\_clearance\_template/handler.py                         |       34 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/version\_clearance\_template/route.py                           |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/version\_clearance\_template/tool.py                            |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/withdraw\_clearance\_template/\_\_init\_\_.py                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/withdraw\_clearance\_template/command.py                        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/withdraw\_clearance\_template/decider.py                        |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/safety/features/withdraw\_clearance\_template/handler.py                        |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/safety/features/withdraw\_clearance\_template/route.py                          |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/features/withdraw\_clearance\_template/tool.py                           |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/projections/\_\_init\_\_.py                                              |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/projections/clearance.py                                                 |       71 |        0 |       28 |        0 |    100.0% |           |
| src/cora/safety/projections/clearance\_template.py                                       |       32 |        0 |       10 |        0 |    100.0% |           |
| src/cora/safety/routes.py                                                                |       51 |        0 |        8 |        0 |    100.0% |           |
| src/cora/safety/tools.py                                                                 |       40 |        0 |        0 |        0 |    100.0% |           |
| src/cora/safety/wire.py                                                                  |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/\_\_init\_\_.py                                                          |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/binary\_signal.py                                                        |       21 |        0 |       10 |        0 |    100.0% |           |
| src/cora/shared/bounded\_text.py                                                         |       23 |        0 |        6 |        0 |    100.0% |           |
| src/cora/shared/canonical\_json.py                                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/capture\_phase.py                                                        |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/closed\_value.py                                                         |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/consequence.py                                                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/content\_hash.py                                                         |       32 |        1 |       12 |        1 |     95.5% |       102 |
| src/cora/shared/decision\_signals.py                                                     |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/deprecation.py                                                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/facility\_code.py                                                        |       20 |        0 |        2 |        0 |    100.0% |           |
| src/cora/shared/identifier.py                                                            |       50 |        0 |        4 |        0 |    100.0% |           |
| src/cora/shared/identity.py                                                              |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/json\_merge\_patch.py                                                    |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/shared/json\_schema\_subset.py                                                  |       76 |        0 |       38 |        0 |    100.0% |           |
| src/cora/shared/json\_schema\_validation.py                                              |       80 |        4 |       34 |        1 |     95.6% |140, 257-259 |
| src/cora/shared/justification.py                                                         |       21 |        0 |        8 |        0 |    100.0% |           |
| src/cora/shared/liveness.py                                                              |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/logbook.py                                                               |       31 |        0 |        6 |        0 |    100.0% |           |
| src/cora/shared/path\_segment.py                                                         |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/shared/ports/\_\_init\_\_.py                                                    |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/ports/persistent\_identifier\_minter.py                                  |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/probe\_error.py                                                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/quality.py                                                               |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/reach.py                                                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/scope\_markers.py                                                        |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/steering.py                                                              |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/shared/storage\_root.py                                                         |       14 |        0 |        4 |        0 |    100.0% |           |
| src/cora/shared/text\_bounds.py                                                          |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/\_\_init\_\_.py                                                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/\_bootstrap.py                                                          |        2 |        2 |        0 |        0 |      0.0% |     13-15 |
| src/cora/subject/\_projections.py                                                        |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/\_subject\_update\_handler.py                                           |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/aggregates/\_\_init\_\_.py                                              |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/aggregates/subject/\_\_init\_\_.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/aggregates/subject/events.py                                            |       67 |        0 |       30 |        0 |    100.0% |           |
| src/cora/subject/aggregates/subject/evolver.py                                           |       36 |        0 |       16 |        0 |    100.0% |           |
| src/cora/subject/aggregates/subject/read.py                                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/aggregates/subject/state.py                                             |       83 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/errors.py                                                               |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/\_\_init\_\_.py                                                |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/discard\_subject/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/discard\_subject/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/discard\_subject/decider.py                                    |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/subject/features/discard\_subject/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/discard\_subject/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/discard\_subject/tool.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/dismount\_subject/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/dismount\_subject/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/dismount\_subject/decider.py                                   |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/subject/features/dismount\_subject/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/dismount\_subject/route.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/dismount\_subject/tool.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/get\_subject/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/get\_subject/handler.py                                        |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/subject/features/get\_subject/query.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/get\_subject/route.py                                          |       19 |        0 |        2 |        0 |    100.0% |           |
| src/cora/subject/features/get\_subject/tool.py                                           |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/subject/features/list\_subjects/\_\_init\_\_.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/list\_subjects/handler.py                                      |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/list\_subjects/query.py                                        |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/list\_subjects/route.py                                        |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/list\_subjects/tool.py                                         |       21 |        3 |        0 |        0 |     85.7% |     60-67 |
| src/cora/subject/features/measure\_subject/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/measure\_subject/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/measure\_subject/decider.py                                    |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/subject/features/measure\_subject/handler.py                                    |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/measure\_subject/route.py                                      |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/measure\_subject/tool.py                                       |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/mount\_subject/\_\_init\_\_.py                                 |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/mount\_subject/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/mount\_subject/context.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/mount\_subject/decider.py                                      |       14 |        0 |        6 |        0 |    100.0% |           |
| src/cora/subject/features/mount\_subject/handler.py                                      |       40 |        0 |        4 |        0 |    100.0% |           |
| src/cora/subject/features/mount\_subject/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/mount\_subject/tool.py                                         |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/register\_subject/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/register\_subject/command.py                                   |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/register\_subject/decider.py                                   |       10 |        0 |        2 |        0 |    100.0% |           |
| src/cora/subject/features/register\_subject/handler.py                                   |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/subject/features/register\_subject/route.py                                     |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/register\_subject/tool.py                                      |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/remove\_subject/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/remove\_subject/command.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/remove\_subject/decider.py                                     |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/subject/features/remove\_subject/handler.py                                     |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/remove\_subject/route.py                                       |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/remove\_subject/tool.py                                        |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/return\_subject/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/return\_subject/command.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/return\_subject/decider.py                                     |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/subject/features/return\_subject/handler.py                                     |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/return\_subject/route.py                                       |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/return\_subject/tool.py                                        |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/store\_subject/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/store\_subject/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/store\_subject/decider.py                                      |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/subject/features/store\_subject/handler.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/store\_subject/route.py                                        |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/features/store\_subject/tool.py                                         |       15 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/projections/\_\_init\_\_.py                                             |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/projections/summary.py                                                  |       32 |        0 |       16 |        0 |    100.0% |           |
| src/cora/subject/routes.py                                                               |       41 |        0 |        8 |        0 |    100.0% |           |
| src/cora/subject/tools.py                                                                |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/subject/wire.py                                                                 |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/\_\_init\_\_.py                                                          |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/\_bootstrap.py                                                           |        2 |        2 |        0 |        0 |      0.0% |     14-16 |
| src/cora/supply/\_monitor.py                                                             |       81 |       12 |       18 |        2 |     85.9% |148, 166-169, 278-284, 290-292 |
| src/cora/supply/\_projections.py                                                         |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/\_supply\_seed.py                                                        |       44 |        0 |       10 |        0 |    100.0% |           |
| src/cora/supply/\_supply\_update\_handler.py                                             |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/adapters/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/adapters/postgres\_supply\_lookup.py                                     |       33 |        1 |        6 |        1 |     94.9% |       133 |
| src/cora/supply/aggregates/\_\_init\_\_.py                                               |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/aggregates/supply/\_\_init\_\_.py                                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/aggregates/supply/events.py                                              |      103 |        4 |       32 |        1 |     94.8% |   486-492 |
| src/cora/supply/aggregates/supply/evolver.py                                             |       30 |        0 |       12 |        0 |    100.0% |           |
| src/cora/supply/aggregates/supply/probes.py                                              |       25 |        1 |        2 |        1 |     92.6% |        81 |
| src/cora/supply/aggregates/supply/read.py                                                |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/aggregates/supply/state.py                                               |      106 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/errors.py                                                                |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/\_\_init\_\_.py                                                 |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/degrade\_supply/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/degrade\_supply/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/degrade\_supply/decider.py                                      |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/features/degrade\_supply/handler.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/degrade\_supply/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/degrade\_supply/tool.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/deregister\_supply/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/deregister\_supply/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/deregister\_supply/decider.py                                   |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/features/deregister\_supply/handler.py                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/deregister\_supply/route.py                                     |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/deregister\_supply/tool.py                                      |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/get\_supply/\_\_init\_\_.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/get\_supply/handler.py                                          |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/supply/features/get\_supply/query.py                                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/get\_supply/route.py                                            |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/supply/features/get\_supply/tool.py                                             |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/supply/features/list\_supplies/\_\_init\_\_.py                                  |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/list\_supplies/handler.py                                       |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/list\_supplies/query.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/list\_supplies/route.py                                         |       26 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/list\_supplies/tool.py                                          |       27 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_available/\_\_init\_\_.py                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_available/command.py                              |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_available/decider.py                              |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_available/handler.py                              |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_available/route.py                                |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_available/tool.py                                 |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_recovering/\_\_init\_\_.py                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_recovering/command.py                             |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_recovering/decider.py                             |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_recovering/handler.py                             |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_recovering/route.py                               |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_recovering/tool.py                                |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_unavailable/\_\_init\_\_.py                       |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_unavailable/command.py                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_unavailable/decider.py                            |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_unavailable/handler.py                            |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_unavailable/route.py                              |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/mark\_supply\_unavailable/tool.py                               |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/observe\_supply\_status/\_\_init\_\_.py                         |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/observe\_supply\_status/command.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/observe\_supply\_status/decider.py                              |       32 |        0 |       16 |        0 |    100.0% |           |
| src/cora/supply/features/observe\_supply\_status/handler.py                              |       13 |        1 |        0 |        0 |     92.3% |        33 |
| src/cora/supply/features/observe\_supply\_status/route.py                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/observe\_supply\_status/tool.py                                 |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/register\_supply/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/register\_supply/command.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/register\_supply/decider.py                                     |       18 |        0 |        6 |        0 |    100.0% |           |
| src/cora/supply/features/register\_supply/handler.py                                     |       37 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/features/register\_supply/route.py                                       |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/register\_supply/tool.py                                        |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/restore\_supply/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/restore\_supply/command.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/restore\_supply/decider.py                                      |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/features/restore\_supply/handler.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/restore\_supply/route.py                                        |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/features/restore\_supply/tool.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/ports/\_\_init\_\_.py                                                    |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/ports/supply\_observer.py                                                |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/projections/\_\_init\_\_.py                                              |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/projections/supply.py                                                    |       28 |        0 |        4 |        0 |    100.0% |           |
| src/cora/supply/routes.py                                                                |       42 |        0 |        8 |        0 |    100.0% |           |
| src/cora/supply/tools.py                                                                 |       24 |        0 |        0 |        0 |    100.0% |           |
| src/cora/supply/wire.py                                                                  |       14 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/\_\_init\_\_.py                                                           |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/\_authorization\_decision.py                                              |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/\_bootstrap.py                                                            |       34 |        0 |       14 |        0 |    100.0% |           |
| src/cora/trust/\_projections.py                                                          |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/\_visit\_update\_handler.py                                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/adapters/\_\_init\_\_.py                                                  |        2 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/adapters/postgres\_consequence\_lookup.py                                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/\_\_init\_\_.py                                                |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/conduit/\_\_init\_\_.py                                        |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/conduit/entries.py                                             |       27 |        1 |        4 |        1 |     93.5% |       119 |
| src/cora/trust/aggregates/conduit/events.py                                              |       37 |        0 |       10 |        0 |    100.0% |           |
| src/cora/trust/aggregates/conduit/evolver.py                                             |       27 |        0 |       10 |        0 |    100.0% |           |
| src/cora/trust/aggregates/conduit/read.py                                                |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/conduit/state.py                                               |       31 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/policy/\_\_init\_\_.py                                         |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/policy/events.py                                               |       32 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/aggregates/policy/evolver.py                                              |       18 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/aggregates/policy/read.py                                                 |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/policy/state.py                                                |       44 |        0 |        8 |        0 |    100.0% |           |
| src/cora/trust/aggregates/ratification/\_\_init\_\_.py                                   |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/ratification/events.py                                         |       36 |        3 |       10 |        1 |     91.3% |   133-135 |
| src/cora/trust/aggregates/ratification/evolver.py                                        |       22 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/aggregates/ratification/read.py                                           |       11 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/ratification/state.py                                          |       43 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/surface/\_\_init\_\_.py                                        |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/surface/events.py                                              |       25 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/aggregates/surface/evolver.py                                             |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/aggregates/surface/read.py                                                |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/surface/state.py                                               |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/surface/surface\_kind.py                                       |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/visit/\_\_init\_\_.py                                          |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/visit/events.py                                                |      110 |        1 |       52 |        1 |     98.8% |       515 |
| src/cora/trust/aggregates/visit/evolver.py                                               |       58 |        0 |       26 |        0 |    100.0% |           |
| src/cora/trust/aggregates/visit/read.py                                                  |       20 |        7 |        2 |        0 |     59.1% |34-36, 64-74 |
| src/cora/trust/aggregates/visit/state.py                                                 |       95 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/zone/\_\_init\_\_.py                                           |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/zone/events.py                                                 |       24 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/aggregates/zone/evolver.py                                                |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/aggregates/zone/read.py                                                   |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/aggregates/zone/state.py                                                  |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/authorize.py                                                              |       65 |        0 |       18 |        0 |    100.0% |           |
| src/cora/trust/build\_authorize.py                                                       |       18 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/errors.py                                                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/\_\_init\_\_.py                                                  |        0 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/abort\_visit/\_\_init\_\_.py                                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/abort\_visit/command.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/abort\_visit/decider.py                                          |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/abort\_visit/handler.py                                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/abort\_visit/route.py                                            |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/abort\_visit/tool.py                                             |       18 |        1 |        0 |        0 |     94.4% |        55 |
| src/cora/trust/features/cancel\_visit/\_\_init\_\_.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/cancel\_visit/command.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/cancel\_visit/decider.py                                         |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/cancel\_visit/handler.py                                         |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/cancel\_visit/route.py                                           |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/cancel\_visit/tool.py                                            |       18 |        1 |        0 |        0 |     94.4% |        55 |
| src/cora/trust/features/check\_in\_visit/\_\_init\_\_.py                                 |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_in\_visit/command.py                                      |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_in\_visit/decider.py                                      |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/check\_in\_visit/handler.py                                      |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_in\_visit/route.py                                        |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_in\_visit/tool.py                                         |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_out\_visit/\_\_init\_\_.py                                |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_out\_visit/command.py                                     |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_out\_visit/decider.py                                     |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/check\_out\_visit/handler.py                                     |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_out\_visit/route.py                                       |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/check\_out\_visit/tool.py                                        |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/close\_visit\_presence/\_\_init\_\_.py                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/close\_visit\_presence/command.py                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/close\_visit\_presence/decider.py                                |       10 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/close\_visit\_presence/handler.py                                |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/close\_visit\_presence/route.py                                  |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/close\_visit\_presence/tool.py                                   |       17 |        1 |        0 |        0 |     94.1% |        49 |
| src/cora/trust/features/complete\_visit/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/complete\_visit/command.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/complete\_visit/decider.py                                       |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/complete\_visit/handler.py                                       |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/complete\_visit/route.py                                         |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/complete\_visit/tool.py                                          |       17 |        1 |        0 |        0 |     94.1% |        44 |
| src/cora/trust/features/define\_conduit/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_conduit/command.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_conduit/decider.py                                       |       11 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/define\_conduit/handler.py                                       |       32 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/define\_conduit/route.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_conduit/tool.py                                          |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_policy/\_\_init\_\_.py                                   |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_policy/command.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_policy/decider.py                                        |       12 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/define\_policy/handler.py                                        |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/define\_policy/route.py                                          |       19 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_policy/tool.py                                           |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_surface/\_\_init\_\_.py                                  |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_surface/command.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_surface/decider.py                                       |        9 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/define\_surface/handler.py                                       |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/define\_surface/route.py                                         |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_surface/tool.py                                          |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_zone/\_\_init\_\_.py                                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_zone/command.py                                          |        3 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_zone/decider.py                                          |        9 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/define\_zone/handler.py                                          |       31 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/define\_zone/route.py                                            |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/define\_zone/tool.py                                             |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/deny\_ratification/\_\_init\_\_.py                               |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/deny\_ratification/command.py                                    |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/deny\_ratification/decider.py                                    |       16 |        0 |        8 |        0 |    100.0% |           |
| src/cora/trust/features/deny\_ratification/handler.py                                    |       32 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/deny\_ratification/route.py                                      |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/deny\_ratification/tool.py                                       |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/evaluate\_policy/\_\_init\_\_.py                                 |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/evaluate\_policy/handler.py                                      |       34 |        0 |        8 |        0 |    100.0% |           |
| src/cora/trust/features/evaluate\_policy/query.py                                        |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/evaluate\_policy/route.py                                        |       22 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/evaluate\_policy/tool.py                                         |       24 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/get\_surface/\_\_init\_\_.py                                     |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/get\_surface/handler.py                                          |       23 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/get\_surface/query.py                                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/get\_surface/route.py                                            |       19 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/get\_surface/tool.py                                             |       21 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/grant\_ratification/\_\_init\_\_.py                              |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/grant\_ratification/command.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/grant\_ratification/decider.py                                   |       12 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/grant\_ratification/handler.py                                   |       32 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/grant\_ratification/route.py                                     |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/grant\_ratification/tool.py                                      |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/hold\_visit/\_\_init\_\_.py                                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/hold\_visit/command.py                                           |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/hold\_visit/decider.py                                           |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/hold\_visit/handler.py                                           |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/hold\_visit/route.py                                             |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/hold\_visit/tool.py                                              |       18 |        1 |        0 |        0 |     94.4% |        55 |
| src/cora/trust/features/list\_conduits/\_\_init\_\_.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_conduits/handler.py                                        |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_conduits/query.py                                          |       12 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_conduits/route.py                                          |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_conduits/tool.py                                           |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_permissions/\_\_init\_\_.py                                |        5 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_permissions/handler.py                                     |       35 |        0 |        8 |        0 |    100.0% |           |
| src/cora/trust/features/list\_permissions/query.py                                       |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_permissions/route.py                                       |       19 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/list\_permissions/tool.py                                        |       22 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/list\_policies/\_\_init\_\_.py                                   |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_policies/handler.py                                        |       22 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_policies/query.py                                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_policies/route.py                                          |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_policies/tool.py                                           |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_zones/\_\_init\_\_.py                                      |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_zones/handler.py                                           |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_zones/query.py                                             |        7 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_zones/route.py                                             |       20 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/list\_zones/tool.py                                              |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/record\_visit\_arrival/\_\_init\_\_.py                           |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/record\_visit\_arrival/command.py                                |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/record\_visit\_arrival/decider.py                                |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/record\_visit\_arrival/handler.py                                |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/record\_visit\_arrival/route.py                                  |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/record\_visit\_arrival/tool.py                                   |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/register\_visit/\_\_init\_\_.py                                  |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/register\_visit/command.py                                       |        9 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/register\_visit/context.py                                       |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/register\_visit/decider.py                                       |       15 |        0 |       10 |        0 |    100.0% |           |
| src/cora/trust/features/register\_visit/handler.py                                       |       33 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/register\_visit/route.py                                         |       23 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/register\_visit/tool.py                                          |       21 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/release\_control\_of\_surface/\_\_init\_\_.py                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/release\_control\_of\_surface/command.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/release\_control\_of\_surface/context.py                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/release\_control\_of\_surface/decider.py                         |       14 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/release\_control\_of\_surface/handler.py                         |       37 |        2 |        2 |        1 |     92.3% |     80-90 |
| src/cora/trust/features/release\_control\_of\_surface/route.py                           |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/release\_control\_of\_surface/tool.py                            |       17 |        1 |        0 |        0 |     94.1% |        54 |
| src/cora/trust/features/request\_ratification/\_\_init\_\_.py                            |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/request\_ratification/command.py                                 |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/request\_ratification/decider.py                                 |       11 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/request\_ratification/handler.py                                 |       30 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/request\_ratification/route.py                                   |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/request\_ratification/tool.py                                    |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/resume\_visit/\_\_init\_\_.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/resume\_visit/command.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/resume\_visit/decider.py                                         |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/resume\_visit/handler.py                                         |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/resume\_visit/route.py                                           |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/resume\_visit/tool.py                                            |       17 |        1 |        0 |        0 |     94.1% |        45 |
| src/cora/trust/features/revoke\_grant/\_\_init\_\_.py                                    |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/revoke\_grant/command.py                                         |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/revoke\_grant/decider.py                                         |       14 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/revoke\_grant/handler.py                                         |       33 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/revoke\_grant/route.py                                           |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/revoke\_grant/tool.py                                            |       18 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/start\_visit/\_\_init\_\_.py                                     |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/start\_visit/command.py                                          |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/start\_visit/decider.py                                          |        9 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/features/start\_visit/handler.py                                          |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/start\_visit/route.py                                            |       13 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/start\_visit/tool.py                                             |       17 |        1 |        0 |        0 |     94.1% |        44 |
| src/cora/trust/features/take\_control\_of\_surface/\_\_init\_\_.py                       |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/take\_control\_of\_surface/command.py                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/take\_control\_of\_surface/context.py                            |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/take\_control\_of\_surface/decider.py                            |       15 |        0 |        8 |        0 |    100.0% |           |
| src/cora/trust/features/take\_control\_of\_surface/handler.py                            |       37 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/features/take\_control\_of\_surface/route.py                              |       17 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/take\_control\_of\_surface/tool.py                               |       17 |        1 |        0 |        0 |     94.1% |        54 |
| src/cora/trust/features/void\_visit/\_\_init\_\_.py                                      |        6 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/void\_visit/command.py                                           |        4 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/void\_visit/decider.py                                           |       13 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/features/void\_visit/handler.py                                           |       10 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/void\_visit/route.py                                             |       16 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/features/void\_visit/tool.py                                              |       18 |        1 |        0 |        0 |     94.4% |        56 |
| src/cora/trust/projections/\_\_init\_\_.py                                               |        8 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/projections/conduit.py                                                    |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/projections/policy.py                                                     |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/projections/ratification\_coverage.py                                     |       18 |        0 |        4 |        0 |    100.0% |           |
| src/cora/trust/projections/surface\_active\_visit.py                                     |       36 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/projections/visit.py                                                      |       43 |        0 |       18 |        0 |    100.0% |           |
| src/cora/trust/projections/visit\_presence.py                                            |       29 |        0 |        6 |        0 |    100.0% |           |
| src/cora/trust/projections/zone.py                                                       |       14 |        0 |        2 |        0 |    100.0% |           |
| src/cora/trust/routes.py                                                                 |       74 |        2 |       12 |        0 |     97.7% |   167-168 |
| src/cora/trust/tools.py                                                                  |       60 |        0 |        0 |        0 |    100.0% |           |
| src/cora/trust/wire.py                                                                   |       11 |        0 |        0 |        0 |    100.0% |           |
| **TOTAL**                                                                                | **60888** | **1381** | **9260** |  **415** | **97.2%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/xmap/cora/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/xmap/cora/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/xmap/cora/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/xmap/cora/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fxmap%2Fcora%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/xmap/cora/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.