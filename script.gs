function fetchEmailsWithAttachments() {
  const SHEET_ID = '10ubu2xPppsNRCMGo-63ZwpCVhCBxhRyzgfnLqduF71w';
  const SHEET_NAME = 'gmail';
  const EMAIL_API_URL = PropertiesService.getScriptProperties().getProperty('EMAIL_API_URL');
  const ATTACHMENT_API_URL = PropertiesService.getScriptProperties().getProperty('ATTACHMENT_API_URL');
  const SUPABASE_URL = PropertiesService.getScriptProperties().getProperty('SUPABASE_URL');
  const SUPABASE_SERVICE_KEY = PropertiesService.getScriptProperties().getProperty('SUPABASE_SERVICE_KEY');
  const PDF_BUCKET_NAME = 'attachments';
  const API_KEY = PropertiesService.getScriptProperties().getProperty('API_KEY');

  const START_DATE = '2023/09/12'; // Updated to a past date
  const END_DATE = '2023/09/20';

  // Access the Google Sheet and the specific sheet/tab
  const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
  const sheet = spreadsheet.getSheetByName(SHEET_NAME);
  
  const headers = [
    'Email ID', 'Thread ID', 'From', 'To', 'Subject', 'Body',
    'Attachment Name', 'Attachment URL', 'Timestamp', 'Status', 'Error'
  ];

  // Set Headers if the sheet is empty
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
  }

  // Define Gmail search query for the fixed date range and attachments
  const QUERY = `after:${START_DATE} before:${END_DATE} has:attachment`;
  const threads = GmailApp.search(QUERY);

  if (threads.length === 0) {
    Logger.log('No threads found.');
    return;
  }

  threads.forEach(thread => {
    const messages = thread.getMessages();
    messages.forEach((message, msgIndex) => {
      const emailId = message.getId();
      const from = message.getFrom();
      const to = message.getTo();
      const subject = message.getSubject();
      const body = message.getPlainBody();
      const receivedDate = message.getDate().toISOString();
      const hasAttachments = message.getAttachments().length > 0;

      // Insert email metadata using the API URL to Vercel deployment
      const emailPayload = {
        email_id: emailId,
        from_email: from,
        to_email: to,
        subject: subject,
        body: body,
        received_date: receivedDate,
        has_attachments: hasAttachments,
        processed: false,
        error: null
      };

      const emailResponse = UrlFetchApp.fetch(EMAIL_API_URL, {
        method: 'post',
        contentType: 'application/json',
        headers: {
          'X-API-Key': API_KEY
        },
        payload: JSON.stringify(emailPayload),
        muteHttpExceptions: true
      });
      
      console.log('Email insertion response code:', emailResponse.getResponseCode());
      console.log('Email insertion response headers:', emailResponse.getAllHeaders());
      console.log('Email insertion response:', emailResponse.getContentText());
      console.log('API Key sent:', API_KEY);
      console.log('API Key length:', API_KEY.length);

      let status = 'Success';
      let error = null;

      if (emailResponse.getResponseCode() !== 200) {
        status = 'Failed';
        error = `Status Code: ${emailResponse.getResponseCode()}, Content: ${emailResponse.getContentText()}`;
        console.log('Email insertion error:', error);
        console.log('Request details:', JSON.stringify({
          url: EMAIL_API_URL,
          method: 'POST',
          headers: {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
          },
          payload: emailPayload
        }, null, 2));
      }

      // Process attachments
      const attachments = message.getAttachments();
      attachments.forEach(att => {
        const attachmentName = att.getName();
        const uniqueId = Utilities.getUuid();
        const uniqueAttachmentName = `${attachmentName}_${uniqueId}`;
        const attachmentData = att.getBytes();
        const attachmentType = att.getContentType();
        const attachmentSize = attachmentData.length;

        // Upload attachment to Supabase Storage
        const attachmentUrl = uploadToSupabase(uniqueAttachmentName, attachmentData, attachmentType);

        if (!attachmentUrl) {
          status = 'Failed';
          error = `Failed to upload file ${uniqueAttachmentName}`;
        }

        // Log metadata to Google Sheet
        const timestamp = new Date().toISOString();
        sheet.appendRow([emailId, thread.getId(), from, to, subject, body, uniqueAttachmentName, attachmentUrl, timestamp, status, error]);

        // Insert attachment metadata using the API URL to Vercel deployment if upload succeeded
        if (attachmentUrl) {
          const attachmentPayload = {
            email_id: emailId,
            file_name: uniqueAttachmentName,
            file_size: attachmentSize,
            file_type: attachmentType,
            storage_path: `${PDF_BUCKET_NAME}/${uniqueAttachmentName}`,
            processed: false,
            error: null,
            public_url: attachmentUrl
          };

          const attachmentResponse = UrlFetchApp.fetch(ATTACHMENT_API_URL, {
            method: 'post',
            contentType: 'application/json',
            headers: {
              'X-API-Key': API_KEY
            },
            payload: JSON.stringify(attachmentPayload),
            muteHttpExceptions: true
          });
          console.log('Attachment insertion response:', attachmentResponse.getContentText());
        }
      });
    });
  });

  Logger.log('Email and attachment processing completed.');
}

function uploadToSupabase(fileName, fileData, contentType) {
  const SUPABASE_URL = 'https://pbuqlylgktjdhjqkvwnv.supabase.co';
  const SUPABASE_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBidXFseWxna3RqZGhqcWt2d252Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcyNTIzMzA5NCwiZXhwIjoyMDQwODA5MDk0fQ.NIQG_erHl4XOpknbn2qw6C0U3wo0jwImzywLoxG1aeU';
  const PDF_BUCKET_NAME = 'attachments';

  const url = `${SUPABASE_URL}/storage/v1/object/${PDF_BUCKET_NAME}/${fileName}`;
  const options = {
    method: 'POST',
    headers: {
      "Content-Type": contentType,
      "Authorization": `Bearer ${SUPABASE_SERVICE_KEY}`
    },
    payload: fileData,
    muteHttpExceptions: true
  };
  const response = UrlFetchApp.fetch(url, options);
  const statusCode = response.getResponseCode();

  if (statusCode === 200 || statusCode === 201) {
    Logger.log(`File ${fileName} uploaded successfully.`);
    return `${SUPABASE_URL}/storage/v1/object/public/${PDF_BUCKET_NAME}/${fileName}`;
  } else {
    Logger.log(`Failed to upload file ${fileName}. Status Code: ${statusCode}, Response: ${response.getContentText()}`);
    return null;
  }
}