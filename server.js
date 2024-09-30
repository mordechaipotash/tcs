const { createClient } = require('@supabase/supabase-js');
const express = require('express');
const { json } = require('body-parser');
const { Pool } = require('pg');

const app = express();

require('dotenv').config();

console.log('Starting server...');
console.log('Node version:', process.version);
console.log('Environment variables:', JSON.stringify({
  POSTGRES_USER: process.env.POSTGRES_USER,
  POSTGRES_HOST: process.env.POSTGRES_HOST,
  POSTGRES_DATABASE: process.env.POSTGRES_DATABASE,
  PORT: process.env.PORT,
  SUPABASE_URL: process.env.SUPABASE_URL,
  API_KEY: process.env.API_KEY ? 'Set' : 'Not set',
}));

let pool;
try {
  pool = new Pool({
    user: process.env.POSTGRES_USER,
    host: process.env.POSTGRES_HOST,
    database: process.env.POSTGRES_DATABASE,
    password: process.env.POSTGRES_PASSWORD,
    port: process.env.PORT || 5432,
  });
  console.log('PostgreSQL pool created successfully');
} catch (error) {
  console.error('Error creating PostgreSQL pool:', error);
}

let supabase;
try {
  supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
  console.log('Supabase client created successfully');
} catch (error) {
  console.error('Error creating Supabase client:', error);
}

const API_KEY = process.env.API_KEY;

app.use((req, res, next) => {
  console.log('Received request:', req.method, req.url);
  console.log('Headers:', JSON.stringify(req.headers, null, 2));
  next();
});

app.use((req, res, next) => {
    const apiKey = req.get('X-API-Key');
    console.log('Received API Key:', apiKey);
    console.log('Expected API Key:', process.env.API_KEY);
    console.log('API Key match:', apiKey === process.env.API_KEY);
    if (!apiKey || apiKey !== process.env.API_KEY) {
      console.log('Unauthorized access attempt');
      return res.status(401).json({ error: 'Unauthorized', receivedKey: apiKey });
    }
    console.log('API Key validated successfully');
    next();
  });

app.use(json());

app.get('/', (req, res) => {
  res.status(200).send('Server is running');
});

app.post('/insert-email', async (req, res) => {
  console.log('Received email insertion request:', JSON.stringify(req.body, null, 2));
  const { email_id, from_email, to_email, subject, body, received_date, has_attachments, processed, error } = req.body;

  try {
    const result = await pool.query(
      `INSERT INTO emails (email_id, from_email, to_email, subject, body, received_date, has_attachments, processed, error, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW()) RETURNING id`,
      [email_id, from_email, to_email, subject, body, received_date, has_attachments, processed, error]
    );
    console.log('Email inserted successfully:', result.rows[0].id);
    res.status(200).send({ success: true, email_id: result.rows[0].id });
  } catch (err) {
    console.error('Error in /insert-email:', err);
    res.status(500).send({ success: false, error: err.message });
  }
});

app.post('/insert-attachment', async (req, res) => {
  console.log('Received attachment insertion request:', JSON.stringify(req.body, null, 2));
  const { email_id, file_name, file_size, file_type, storage_path, processed, error, public_url } = req.body;

  try {
    await pool.query(
      `INSERT INTO attachments (email_id, file_name, file_size, file_type, storage_path, processed, error, created_at, public_url)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), $8)`,
      [email_id, file_name, file_size, file_type, storage_path, processed, error, public_url]
    );
    console.log('Attachment inserted successfully');
    res.status(200).send({ success: true });
  } catch (err) {
    console.error('Error in /insert-attachment:', err);
    res.status(500).send({ success: false, error: err.message });
  }
});

app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).send('Internal Server Error');
});

module.exports = app;

// If running locally
if (require.main === module) {
  const port = process.env.PORT || 3000;
  app.listen(port, () => {
    console.log(`Server running on port ${port}`);
  });
}