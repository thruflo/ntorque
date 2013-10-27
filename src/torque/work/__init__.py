# Having an ``__init__.py`` file in it makes a directory a Python package.

"""
  
  # Best Case Scenario
  
  1. blpop yields a task id
  2. task is got from the db
  3. POST is made to the webhook
  4. returns 200
  5. task is marked `completed`
  
  # Considerations
  
  1. blpop yields a task id
  
  * handle in a new thread
  
  2. task is got from the db
  
  * do we need to indicate that it has been 'acquired'?
  
  3. POST is made to the webhook
  
  * do we have a timeout?
  * relationship between timeout and retrying
  
  4. returns 200 / 5. task is marked `completed`
  
  * how do we requeue:
    - writing to db?
    - `rpush` to redis after a delay?
  
"""