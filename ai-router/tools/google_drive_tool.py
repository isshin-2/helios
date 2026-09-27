import requests
from typing import Tuple, Dict, Any, List
from pydantic import BaseModel, Field
from tools.base import BaseTool
import json

class GoogleDriveListSchema(BaseModel):
    access_token: str = Field(description="Your Google Drive OAuth Access Token")
    query: str = Field(default="", description="Search query string (e.g. \"name contains 'budget'\")")
    max_results: int = Field(default=10, description="Maximum number of files to return")

class GoogleDriveListTool(BaseTool):
    @property
    def name(self) -> str:
        return "google_drive_list_files"

    @property
    def description(self) -> str:
        return "List or search for files in Google Drive using the REST API."

    @property
    def input_schema(self) -> type[BaseModel]:
        return GoogleDriveListSchema
        
    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        access_token = kwargs.get("access_token")
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 10)
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "pageSize": max_results,
            "fields": "files(id, name, mimeType, modifiedTime)",
        }
        if query:
            params["q"] = query
            
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                files = resp.json().get("files", [])
                return (json.dumps(files, indent=2), self.name)
            else:
                return (f"Google Drive API Error {resp.status_code}: {resp.text}", self.name)
        except Exception as e:
            return (f"Failed to fetch files from Google Drive: {str(e)}", self.name)

class GoogleDriveReadSchema(BaseModel):
    access_token: str = Field(description="Your Google Drive OAuth Access Token")
    file_id: str = Field(description="The ID of the file to read")
    mime_type: str = Field(default="", description="If reading a Google Doc, specify 'text/plain' to export it")

class GoogleDriveReadTool(BaseTool):
    @property
    def name(self) -> str:
        return "google_drive_read_file"

    @property
    def description(self) -> str:
        return "Download or export a file's contents from Google Drive."

    @property
    def input_schema(self) -> type[BaseModel]:
        return GoogleDriveReadSchema
        
    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        access_token = kwargs.get("access_token")
        file_id = kwargs.get("file_id")
        mime_type = kwargs.get("mime_type")
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        try:
            # If it's a native Google Doc, we must use the export endpoint
            if mime_type:
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
                params = {"mimeType": mime_type}
            else:
                # Standard file download
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
                params = {"alt": "media"}
                
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                # Return the first 2000 characters to avoid blowing up the context window
                content = resp.text
                if len(content) > 2000:
                    content = content[:2000] + "\n...[TRUNCATED]..."
                return (content, self.name)
            else:
                return (f"Google Drive API Error {resp.status_code}: {resp.text}", self.name)
        except Exception as e:
            return (f"Failed to read file from Google Drive: {str(e)}", self.name)
