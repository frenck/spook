```yaml [automations.yaml]
# The same automation as in the editor 👻
alias: Weekday morning lights
triggers:
  - trigger: spook.cron
    options:
      schedule: "30 6 * * 1-5"
conditions:
  - condition: spook.cooldown
    options:
      duration: "01:00:00"
actions:
  - action: light.turn_on
    target:
      entity_id: light.kitchen_lights
```
