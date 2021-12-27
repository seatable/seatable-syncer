import React, { Fragment } from 'react';
import ReactDOM from 'react-dom';
import moment from 'moment';

import '@/assets/css/common.css';
import '@/assets/css/sync-jobs.css';

class App extends React.Component {

  renderJobList = () => {
    const { syncerJobs } = window.app.config;
    return (
      <Fragment>
        {syncerJobs && syncerJobs.map(job => {
          return (
            <tr>
              <td width="25%">{job.dtable_uuid}</td>
              <td width="20%">{job.name}</td>
              <td width="10%">{job.job_type}</td>
              <td width="10%">{job.is_valid ? 'true' : 'false'}</td>
              <td width="25%">{moment(job.last_trigger_time).format('YYYY-MM-DD HH:mm:ss')}</td>
              <td width="10%">{job.trigger_detail.trigger_type}</td>
            </tr>
          );
        })}
      </Fragment>
    );
  }

  render() {
    const { message } = window.app.config;
    const logoutUrl = '/login_out/';

    if (message) {
      return <div className="error-message">{message}</div>;
    }

    return (
      <div className="app-container">
        <div className="app-header">
          <div className="title">Sync Jobs</div>
          <div className="logout"><a href={logoutUrl}>Logout</a></div>
        </div>
        <div className="app-content">
          <div className="jobs-container">
            <table>
              <thead>
                <tr>
                  <th width="25%">Bases</th>
                  <th width="20%">Job name</th>
                  <th width="10%">Job type</th>
                  <th width="10%">Is valid</th>
                  <th width="25%">Last trigger time</th>
                  <th width="10%">Trigger type</th>
                </tr>
              </thead>
              <tbody>
                {this.renderJobList()}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }
}

ReactDOM.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
  document.getElementById('root')
);
