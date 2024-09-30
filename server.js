const { createClient } = require('@supabase/supabase-js');
const express = require('express');
const { json } = require('body-parser');
const { Pool } = require('pg');
const app = express();

require('dotenv').config();

const pool = new Pool({
  user: process.env.POSTGRES_USER,
  host: process.env.POSTGRES_HOST,
  database: process.env.POSTGRES_DATABASE,
  password: process.env.POSTGRES_PASSWORD,
  port: process.env.PORT || 5432,
});

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

const API_KEY = process.env.API_KEY;

app.use((req, res, next) => {
  console.log('Received API Key:', req.get('X-API-Key'));
  console.log('Expected API Key:', API_KEY);
  const apiKey = req.get('X-API-Key');
  if (!apiKey || apiKey !== API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

app.use(json());

app.post('/insert-email', async (req, res) => {
  console.log('Received email insertion request:', req.body);
  const { email_id, from_email, to_email, subject, body, received_date, has_attachments, processed, error } = req.body;

  try {
    const result = await pool.query(
      `INSERT INTO emails (email_id, from_email, to_email, subject, body, received_date, has_attachments, processed, error, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW()) RETURNING id`,
      [email_id, from_email, to_email, subject, body, received_date, has_attachments, processed, error]
    );
    res.status(200).send({ success: true, email_id: result.rows[0].id });
  } catch (err) {
    console.error(err);
    res.status(500).send({ success: false, error: err.message });
  }
});

app.post('/insert-attachment', async (req, res) => {
  console.log('Received attachment insertion request:', req.body);
  const { email_id, file_name, file_size, file_type, storage_path, processed, error, public_url } = req.body;

  try {
    await pool.query(
      `INSERT INTO attachments (email_id, file_name, file_size, file_type, storage_path, processed, error, created_at, public_url)
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), $8)`,
      [email_id, file_name, file_size, file_type, storage_path, processed, error, public_url]
    );
    res.status(200).send({ success: true });
  } catch (err) {
    console.error(err);
    res.status(500).send({ success: false, error: err.message });
  }
});

module.exports = app;