# -*- coding: utf-8 -*-

"""Include this module before pyramid_basemodel to tell sqlalchemy
  to use the winnow json utililies with the JSON type.

  XXX this is pretty nuclear -- i.e.: it stores all JSON numbers
  as decimals. It also doesn't involve using the main Pyramid json
  renderer, which we may want to use *as well as* the winnow utils.
"""

import winnow

def kwargs_factory(registry):
    return {
        "json_serializer" : winnow.utils.json_dumps,
        "json_deserializer" : winnow.utils.json_loads
    }

def includeme(config):
    settings = config.get_settings()
    settings.setdefault('sqlalchemy.engine_kwargs_factory', kwargs_factory)
