# Dify Workflow DSL Node Types Reference

> Source: https://github.com/mango-svip/dify-workflow-skills/blob/HEAD/references/node_types.md
> Based on actual Dify code implementation (v1.14+)

## 1. start
- **data.type**: `"start"`
- **Required fields**: `type`, `title`, `variables` (array of input definitions)
- **Variable fields**: `variable`, `label`, `type` (text, paragraph, number, select), `required`, `max_length`, `options`
- **Common errors**: Missing `variables` array; invalid type value; missing `variable` name
- **Example**:
```yaml
type: start
title: Start
variables:
  - label: User Input
    max_length: 10000
    required: true
    type: paragraph
    variable: user_input
```

## 2. end
- **data.type**: `"end"`
- **Required fields**: `type`, `title`, `outputs` (array of output selectors)
- **Output fields**: `variable`, `value_selector` (array path like `['node_id', 'field']`)
- **Common errors**: Empty `outputs`; invalid `value_selector` path
- **Example**:
```yaml
type: end
title: End
outputs:
  - variable: result
    value_selector:
      - '1733478262179'
      - text
```

## 3. llm
- **data.type**: `"llm"`
- **Required fields**: `type`, `title`, `model`, `prompt_template`
- **Model fields**: `provider`, `name`, `mode` (chat/completion), `completion_params`
- **Prompt fields**: `id`, `role` (system/user/assistant), `text` with `{{#node_id.field#}}` references
- **Common errors**: Invalid model provider; missing prompt template; malformed variable refs

## 4. code
- **data.type**: `"code"`
- **Required fields**: `type`, `title`, `code`, `code_language` (python3/javascript), `variables`, `outputs`
- **Variables**: Array of `[node_id, field_name]` selectors
- **Outputs**: Named outputs with `type` (string, number, object, boolean, array_*) and `children: null`
- **Common errors**: Missing `code_language`; invalid output type; `outputs` children null when required
- **Example**:
```yaml
type: code
title: Process Data
code: |
  def main(input_text: str) -> dict:
      return {'output': input_text.upper()}
code_language: python3
variables:
  - - '1733478262179'
    - text
outputs:
  output:
    type: string
    children: null
```

## 5. variable-aggregator
- **data.type**: `"variable-aggregator"`
- **Required fields**: `type`, `title`, `variables`, `output_type`
- **Fields**: `variables` (array of `[node_id, var_name]` paths), `output_type` (string, number, object, array)
- **Common errors**: Missing `output_type`; incompatible upstream branch types
- **Example**:
```yaml
type: variable-aggregator
title: Merge Results
output_type: object
variables:
  - - '1733478343153'
    - result
  - - '17334785192390'
    - result
```

## 6. if-else
- **data.type**: `"if-else"`
- **Required fields**: `type`, `title`, `cases` (new) or `conditions`+`logical_operator` (legacy)
- **Case fields**: `case_id`, `logical_operator` (and/or), `conditions` array
- **Condition fields**: `variable_selector`, `comparison_operator`, `value`, `sub_variable_condition`
- **Operators**: String ("contains", "is", "empty", etc.), Number ("=", "≠", ">", "<"), File ("exists")
- **Source handles**: `true`, `false`
- **Common errors**:
  - Invalid operator for variable type
  - Missing `case_id`
  - **For boolean variables**: `is` operator + empty value causes "变量值不能为空" error. Workaround: convert boolean to string in code node, or use `empty`/`not empty` operators
- **Example**:
```yaml
type: if-else
title: Check Condition
cases:
  - case_id: case_1
    logical_operator: and
    conditions:
      - variable_selector:
          - '1733478262179'
          - text
        comparison_operator: contains
        value: "error"
```

## 7. iteration
- **data.type**: `"iteration"`
- **Required fields**: `type`, `title`, `input_selector`, `output_selector`
- **Common errors**: `input_selector` points to non-array; missing `output_selector`

## 8. knowledge-retrieval
- **data.type**: `"knowledge-retrieval"`
- **Required fields**: `type`, `title`, `dataset_ids`, `query_variable_selector`, `retrieval_mode`
- **Retrieval modes**: `multiple` (vector) or `single`
- **Common errors**: Invalid dataset IDs; missing query selector; dataset not indexed

## 9. http-request
- **data.type**: `"http-request"`
- **Required fields**: `type`, `title`, `method`, `url`, `authorization`, `headers`, `params`, `body`
- **Outputs**: `body`, `status_code`, `headers`, `files`

## 10. template-transform
- **data.type**: `"template-transform"`
- **Required fields**: `type`, `title`, `template`, `variables`

## 11. answer
- **data.type**: `"answer"`
- **Required fields**: `type`, `title`, `answer` (template string)

## 12. loop
- **data.type**: `"loop"`
- **Required fields**: `type`, `title`, `loop_count`, `break_conditions`, `logical_operator`
- **Source handles**: `loop` (continue), `source` (exit)

## 13. tool
- **data.type**: `"tool"`
- **Required fields**: `type`, `title`, `provider_id`, `provider_type`, `tool_name`, `tool_parameters`

## 14. parameter-extractor
- **data.type**: `"parameter-extractor"`
- **Required fields**: `type`, `title`, `model`, `query`, `parameters`

## 15. variable-assigner (assigner)
- **data.type**: `"variable-assigner"` or `"assigner"`

## 16. question-classifier
- **data.type**: `"question-classifier"`
- **Required fields**: `type`, `title`, `model`, `query_variable_selector`, `classes`

## 17. document-extractor
- **data.type**: `"document-extractor"`
- **Required fields**: `type`, `title`, `variable_selector`

## 18. agent
- **data.type**: `"agent"`
- **Required fields**: `type`, `title`, `model`, `tools`, `prompt`

## Variable Reference Syntax
Variables use `{{#node_id.field_name#}}` format, e.g., `{{#1732007415808.user_input#}}`.

## Error Handling Strategies
- **fail-branch**: Creates `success-branch`/`fail-branch` paths; exposes `error_message`, `error_type`
- **default-value**: Returns predefined value; continues main path
- **retry-config**: `max_retries`, `retry_interval` (ms)
- **abort** (default): Workflow stops on error

## Common Pitfalls in this project

### 1. if-else + boolean variable
**Error**: "变量值不能为空"
**Cause**: Dify if-else `is` operator requires non-empty `value` for any comparison. When checking `True`/`False`, the value field must contain a string like "true" not empty.
**Fix**: Use `comparison_operator: empty` or `not empty` for boolean checks; OR have code node return string "true"/"false" instead of Python bool.

### 2. variable-aggregator with mixed types
**Error**: Validation error "Input should be a valid list"
**Cause**: VA variables must all be `[node_id, var_name]` lists, not `{variable, value_selector}` dicts
**Fix**: Use `[[node_id, var_name], [node_id, var_name]]` format

### 3. code node inline source
**Error**: ModuleNotFoundError on `charge_consult` import
**Cause**: Dify sandbox cannot import user modules; only system packages available
**Fix**: Inline all function code into the code node string; use plain Python (no Pydantic)

### 4. Outputs schema mismatch
**Error**: "outputs.type Input should be a valid dictionary"
**Cause**: Dify 1.14 expects `{field_name: {type, children: null}}` not `{type: object, properties: [...]}`
**Fix**: Use dict format with `type` and `children: null` per field
