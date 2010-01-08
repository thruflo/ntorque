
0.4.3
-----

* enabled processing in a thread, via the ``async=True|False`` option to ``QueueProcessor.start`` method
* provided ``./bin/torque-run`` to run the webapp and processor in seperate threads of a single OS process


0.4.2
-----

* added ``sort_keys=True`` to the ``torque.client.Task.__init__`` json
  encoding to ensure the task_string hash yeilds a consistent task id

