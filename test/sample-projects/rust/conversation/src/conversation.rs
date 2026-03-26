use std::collections::VecDeque;

pub fn helper(name: &str) -> String {
    format!("hello {name}")
}

pub fn run() {
    helper("world");
}

pub struct Conversation {
    messages: VecDeque<String>,
}

impl Conversation {
    pub fn new() -> Self {
        Conversation {
            messages: VecDeque::new(),
        }
    }

    pub fn append(&mut self, message: String) {
        self.messages.push_back(message);
        helper("append");
    }
}

pub enum Status {
    Idle,
    Active,
}

pub trait Runnable {
    fn execute(&self);
}
