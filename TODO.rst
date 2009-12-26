
* check the Task api, specifically the serialise / deserialise in and out of string format: should this be handled by the Task class?  surely the task_string awareness in the view code is bad?

* double check the set behaviour: i.e.: are there any race conditions we need to worry about?

* is the import chain sane - can we simplify?

* debug it and check it works

* update the README with some explanation of the point & motivation and check the docstrings make sense - can we use them as tests?

* pypi it
