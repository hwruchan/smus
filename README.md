# SMU Schedule MCP Server

[![smithery badge](https://smithery.ai/badge/@hwruchan/smus)](https://smithery.ai/server/@hwruchan/smus)

A Model Context Protocol (MCP) server for managing SMU (Sangmyung University) schedules, meals, notices, and exam information.

## Features

### Tools
- **now_kr**: Get current date/time in Asia/Seoul timezone
- **query_smu_meals_by_date_category**: Query SMU meals by date and category (breakfast/lunch/dinner)
- **query_smu_meals_by_keyword**: Search SMU meals by keyword
- **query_smu_notices_by_keyword**: Search SMU notices by keyword in title
- **query_smu_exam**: Search SMU exam information by subject name and optional professor
- **query_smu_schedule_by_keyword**: Search SMU schedule by keyword in content
- **query_special_keywords**: Get predefined responses for special keywords
- **add_smu_schedule_structured**: Add a new schedule to SMU schedule database
- **delete_smu_schedule_by_content**: Delete schedules by content keyword

### Prompts
- **default_prompt**: Default system prompt for SMU chat assistant with timezone handling

## Requirements

- Python 3.11+
- MySQL database with SMU data
- Required environment variables:
  - `DB_HOST`: MySQL database host
  - `DB_USER`: MySQL database user
  - `DB_PASSWORD`: MySQL database password (required)
  - `DB_NAME`: MySQL database name
  - `DB_PORT`: MySQL database port (default: 3306)

## Usage

### Installing via Smithery

To install SMU Schedule MCP Server automatically via [Smithery](https://smithery.ai/server/@hwruchan/smus):

```bash
npx -y @smithery/cli install @hwruchan/smus
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DB_HOST="your-db-host"
export DB_USER="your-db-user"
export DB_PASSWORD="your-db-password"
export DB_NAME="your-db-name"

# Run the server
python lastdance1008.py
```

### Docker

```bash
# Build image
docker build -t smu-schedule-mcp .

# Run container
docker run -e DB_HOST=your-host \
           -e DB_USER=your-user \
           -e DB_PASSWORD=your-password \
           -e DB_NAME=your-db \
           smu-schedule-mcp
```

## Database Schema

The server expects the following tables:
- `smu_meals`: Meal information with date, category, and meal content
- `smu_notices`: Notice information with title and URL
- `smu_exam`: Exam information with subject_name and professor
- `smu_schedule`: Schedule information with start_date, end_date, and content

## License

MIT

## Author

hwruchan
