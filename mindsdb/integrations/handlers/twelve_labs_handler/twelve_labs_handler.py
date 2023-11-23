from typing import Optional, Dict

import pandas as pd
from mindsdb.utilities import log

from mindsdb.integrations.libs.base import BaseMLEngine
from mindsdb.integrations.utilities.handler_utils import get_api_key

from mindsdb.integrations.handlers.twelve_labs_handler.twelve_labs_api_client import TwelveLabsAPIClient


logger = log.getLogger(__name__)

# TODO: move to config
BASE_URL = "https://api.twelvelabs.io/v1.1"
DEFAULT_ENGINE = "marengo2.5"
DEFAULT_WAIT_DURATION = 5


class TwelveLabsHandler(BaseMLEngine):
    """
    Integration with the Twelve Labs API.
    """

    name = 'twelve_labs'

    @staticmethod
    def create_validation(target, args=None, **kwargs):
        pass

    def create(self, target: str, df: Optional[pd.DataFrame] = None, args: Optional[Dict] = None) -> None:
        # check for USING clause
        if 'using' not in args:
            # TODO: update Exception to InsufficientParametersException
            raise Exception("Twelve Labs engine requires a USING clause! Refer to its documentation for more details.")

        # get USING args and add target
        args = args['using']
        args['target'] = target

        # get api key
        api_key = get_api_key(
            api_name=self.name,
            create_args=args,
            engine_storage=self.engine_storage,
        )

        # initialize TwelveLabsAPIClient
        twelve_labs_api_client = TwelveLabsAPIClient(api_key=api_key)

        # update args with api key
        args['api_key'] = api_key

        # get index if it exists
        index_id = twelve_labs_api_client.get_index_by_name(index_name=args['index_name'])

        # create index if it doesn't exist
        if not index_id:
            logger.info(f"Index {args['index_name']} does not exist. Creating index.")
            index_id = twelve_labs_api_client.create_index(
                index_name=args['index_name'],
                engine_id=args['engine_id'] if 'engine_id' in args else None,
                index_options=args['index_options'],
                addons=args['addons'] if 'addons' in args else []
            )
        
        else:
            logger.info(f"Index {args['index_name']} already exists. Using existing index.")

        # store index_id in args
        args['index_id'] = index_id

        # create video indexing tasks for all video files or video urls
        # video urls will be given precedence
        # check if video_urls_col has been set and use it to get the video urls
        if 'video_urls_col' in args:
            logger.info("video_urls_col has been set, therefore, it will be given precedence.")
            video_urls = df[args['video_urls_col']].tolist()
        
        # else, check if video_files_col has been set and use it to get the video files
        elif 'video_files_col' in args:
            logger.info("video_urls_col has not been set, therefore, video_files_col will be used.")
            video_files = df[args['video_files_col']].tolist()

        # else, check if video_urls or video_files have been set and use them
        else:
            logger.info("video_urls_col and video_files_col have not been set, therefore, video_urls and video_files will be used.")
            video_urls = args['video_urls'] if 'video_urls' in args else None
            video_files = args['video_files'] if 'video_files' in args else None

        # if video_urls and video_files are not set, then raise an exception
        if not video_urls and not video_files:
            logger.error("Neither video_urls_col, video_files_col, video_urls nor video_files have been set.")
            raise RuntimeError("Neither video_urls_col, video_files_col, video_urls nor video_files have been set. Please set one of them.")

        task_ids = twelve_labs_api_client.create_video_indexing_tasks(
            index_id=index_id,
            video_urls=video_urls,
            video_files=video_files,
        )

        # poll for video indexing tasks to complete
        twelve_labs_api_client.poll_for_video_indexing_tasks(task_ids=task_ids)

        # store args in model_storage
        self.model_storage.json_set('args', args)

    def predict(self, df: Optional[pd.DataFrame] = None, args: Optional[Dict] = None) -> None:
        pass