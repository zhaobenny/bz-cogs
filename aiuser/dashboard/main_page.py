from aiuser.dashboard.decorator import dashboard_page


@dashboard_page(name=None, methods=("GET"), is_owner=True, hidden=True)
async def main(self, **kwargs):
    return {
        "status": 0,
        "web_content": {
            "source": "Not implemented yet.",
        },
    }
