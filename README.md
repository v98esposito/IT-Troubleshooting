# IT Support Ticketing System
> A centralized, robust, and intuitive platform designed to streamline IT support requests and optimize troubleshooting workflows.

## Project Overview
The IT Support Ticketing System centralizes the management of internal technical support requests, eliminating communication bottlenecks and optimizing troubleshooting flows. Built with a strict focus on **Data-Driven Decision Making** and maximum operational efficiency for IT technicians, this platform provides clear insights, Role-Based Access Control (Admin, Manager, IT Staff, Employee), and structured workflows to resolve issues faster.

## Key Features

- **Advanced Ticket Management:** Navigate through support requests effortlessly using a surgical filtering system (filter by status, priority, category, assignee, and date). The interface allows IT staff to claim, reassign, update, and resolve tickets with minimal friction.
- **Reporting & Analytics:** A dedicated analytics dashboard featuring dynamic interactive charts visualizing Ticket Status Distribution, Category Breakdown, and IT Staff Workload.
- **Performance Tracking:** Built-in metrics monitor the Average Resolution Time and ticket throughput, allowing managers to identify bottlenecks and optimize resource allocation.
- **Export Functionality:** Seamlessly print and download comprehensive ticket reports and system analytics for stakeholder meetings or external audits.

## Tech Stack
Built upon a reliable and high-performance architecture:
- **Backend:** Python 3.11+, Flask 3.1
- **Database:** PostgreSQL (via SQLAlchemy & Psycopg2)
- **Frontend & UI:** HTML5, CSS3, Vanilla JavaScript, Bootstrap 5.3 (Custom Dark Theme optimized for reduced eye strain)
- **Data Visualization:** Chart.js integrations for analytics
- **Authentication & Security:** Flask-Login, Flask-WTF, Werkzeug Security

## Installation and Setup

Follow these standard steps to clone the repository and start the development server locally.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/v98esposito/IT-Troubleshooting.git
   cd it-support-ticketing
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Alternatively, since the project includes a `pyproject.toml`, you can set up the environment accordingly).*

4. **Environment Configuration:**
   Configure your Database URI and Flask Secret Key by exporting the required variables or using a `.env` file:
   ```env
   FLASK_APP=main.py
   FLASK_DEBUG=1
   DATABASE_URL=postgresql://user:password@localhost:5432/db_name
   SECRET_KEY=your_secure_secret_key
   ```

5. **Initialize the Database:**
   Ensure your database migrations are applied or the schema is created before running the application for the first time.

6. **Run the Development Server:**
   ```bash
   flask run
   # or
   python main.py
   ```
   The application will be accessible at `http://127.0.0.1:5000`.

## Screenshots

### Analytics Dashboard
![Dashboard Placeholder](attached_assets/dashboard_placeholder.png)
*Illustration of the primary dashboard, emphasizing Data-Driven Decision Making with real-time metrics.*

### Ticket Management List
![Ticket List Placeholder](attached_assets/ticket_list_placeholder.png)
*Surgical filtering system within the Ticket List view.*

## Author & License
**Author:** Internal IT Support Team  
**License:** Proprietary / MIT *(Update according to organizational guidelines)*

---
*Designed to empower operations. Built for IT efficiency.*