export default class Account {
  
  constructor(object) {
    this.id = object.id || null;
    this.host = object.account_config.host || null;
    this.user = object.account_config.user || null;
    this.password = object.account_config.password || null;
    this.port = object.account_config.port || null;
    this.account_name = object.account_config.account_name || null;
    this.owner = object.owner || null;
  }

}
