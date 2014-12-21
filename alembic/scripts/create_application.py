# -*- coding: utf-8 -*-

"""Create an application, with random API key."""

import argparse
import os
import transaction

from ntorque.model import CreateApplication
from ntorque.model import GetActiveKey

from ntorque.work.main import Bootstrap

def parse_args():
    """Parse the command line arguments."""
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--name')
    args = parser.parse_args()
    if not args.name:
        raise ValueError(parser.format_help())
    return args

def main():
    """Main entry point."""
    
    # Bootstrap the pyramid environment.
    bootstrapper = Bootstrap()
    config = bootstrapper()
    config.commit()
    
    # Parse the command line args.
    args = parse_args()
    name = args.name
    
    # Create the app.
    create_app = CreateApplication()
    get_key = GetActiveKey()
    with transaction.manager:
        app = create_app(name)
        api_key = get_key(app).value
    
    print u'Created application with API key: {0}\n'.format(api_key)


if __name__ == '__main__':
    main()

