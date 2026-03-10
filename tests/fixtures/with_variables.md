---
description: Template with required variables
inputs:
  - name: user_name
    required: true
  - name: task
    required: false
---

# Task Assignment

User: {{ user_name }}
{% if task %}Task: {{ task }}{% endif %}

Please complete the assigned task.
