export const ACCOUNT_ATTRIBUTE = {
  ID: 'id',
  HOST: 'host',
  USER: 'user',
  PASSWORD: 'password',
  PORT: 'port',
  ACCOUNT_NAME: 'account_name',
  OWNER: 'owner'
};

export const ACCOUNT_ATTRIBUTE_DISPLAY = [
  { key: ACCOUNT_ATTRIBUTE.HOST, name: 'Host' },
  { key: ACCOUNT_ATTRIBUTE.USER, name: 'User' },
  { key: ACCOUNT_ATTRIBUTE.PASSWORD, name: 'Password' },
  { key: ACCOUNT_ATTRIBUTE.PORT, name: 'Port' },
  { key: ACCOUNT_ATTRIBUTE.ACCOUNT_NAME, name: 'Account name' },
  { key: ACCOUNT_ATTRIBUTE.OWNER, name: 'Owner' },
];

export const ACCOUNT_TYPES = [
  { type: 'mysql', display: 'Mysql' }
];
