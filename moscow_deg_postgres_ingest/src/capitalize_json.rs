use serde_json::{Map, Value};

// Function to capitalize a string
fn capitalize(s: &str) -> String {
    s.char_indices().fold(String::new(), |mut acc, (i, c)| {
        if i == 0 {
            acc.push_str(&c.to_uppercase().to_string());
        } else {
            acc.push(c);
        }
        acc
    })
}

pub trait CapitalizeKeys {
    fn capitalize_keys(&self) -> Self;
}

impl CapitalizeKeys for Value {
    fn capitalize_keys(self: &Value) -> Value {
        match self {
            Value::Object(obj) => {
                let mut new_obj = Map::new();
                for (k, v) in obj {
                    let new_key = capitalize(k);
                    let new_value = v.capitalize_keys();
                    new_obj.insert(new_key, new_value);
                }
                Value::Object(new_obj)
            }
            Value::Array(arr) => {
                let new_arr: Vec<Value> = arr.iter().map(|v| v.capitalize_keys()).collect();
                Value::Array(new_arr)
            }
            // For other types, return a clone as they are not modified
            _ => self.clone(),
        }
    }
}

impl<T: CapitalizeKeys> CapitalizeKeys for Option<T> {
    fn capitalize_keys(self: &Option<T>) -> Option<T> {
        match self {
            Some(v) => Some(v.capitalize_keys()),
            None => None,
        }
    }
}
