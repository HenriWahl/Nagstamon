# Changelog

[1.2.0] - 2021-08-23:
  * changed:
      Removed dependencies to the Prometheus integration
      alertmanager is now a full module residing in its own directory
  * added:
      Support user defined severity values for critical or warning

[1.1.0] - 2021-05-18:
  * changed:
      Using logging module for all outputs
      Some refactoring for testing support
  * added:
      Initial tests based on unittest and pylint (see tests/test_Alertmanager.py)

[1.0.2] - 2021-04-10:
  * added:
      Better debug output

[1.0.1] - 2020-11-27:
  * added:
      Support for hiding suppressed alerts with the scheduled downtime filter

[1.0.0] - 2020-11-08:
  * added:
      Inital version