from pathlib import Path
import re

def to_camel(s: str) -> str:
  parts = [p for p in s.split("_") if p]
  return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])

APIS = [
  "at_array_end", "at_object_end",
  "begin_array", "begin_object", "begin_payload_object", "begin_root_object", "begin_variant",
  "comma_sep",
  "dump_bool", "dump_dict_str_float", "dump_dict_str_int", "dump_dict_str_str", "dump_dict_str_long",
  "dump_field_bool", "dump_field_int", "dump_field_list_float", "dump_field_list_int",
  "dump_field_list_str", "dump_field_list_long", "dump_field_str", "dump_field_long",
  "dump_float", "dump_int", "dump_key", "dump_list_float", "dump_list_int", "dump_list_str",
  "dump_list_long", "dump_str", "dump_long",
  "encode_str", "end_array", "end_object", "end_variant", "expect_char",
  "from_span", "key_at", "value_at",
  "load_dict_str_float", "load_dict_str_int", "load_dict_str_str", "load_dict_str_long",
  "load_float", "load_list_float_value", "load_list_int_value", "load_list_str_value",
  "load_list_long_value", "load_str", "load_str_span", "load_string_slow", "load_tag_field",
  "parse_bool_at", "parse_long_at", "parse_int_at", "parse_int_at_ascii",
  "read_quoted", "set_capacity", "skip_value", "try_match_key",
  "skip_spaces", "src_char", "src_len", "serde_push_slot", "serde_commit_push",
  "str_assign_from_seg", "ascii_ok", "load_list_element", "skip_field",
]

p = Path("src/passes/serializable.py")
t = p.read_text(encoding="utf-8")
orig = t
for old in sorted(APIS, key=len, reverse=True):
  new = to_camel(old)
  t2 = re.sub(rf"\b{re.escape(old)}\b", new, t)
  if t2 != t:
    print(f"  {old} -> {new}")
  t = t2
if t != orig:
  p.write_text(t, encoding="utf-8", newline="\n")
  print("updated")
else:
  print("no change")
pat = re.compile(r"\.([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b")
print("remaining:", sorted(set(pat.findall(t))))
