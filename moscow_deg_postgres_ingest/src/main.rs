mod capitalize_json;
mod voting_row;
mod voting_row_2023;
mod voting_row_2024;

use clap::Parser;
use native_tls::TlsConnector;
use postgres_native_tls::MakeTlsConnector;
use std::env;
use tokio::fs::File;
use tokio::io::AsyncBufReadExt;
use tokio::io::BufReader;
use tokio_postgres::Error;

/*

CREATE TABLE saved_tx_hashes (
    TxHash TEXT,
    RowHash TEXT,
    PRIMARY KEY (TxHash, RowHash)
);

GRANT INSERT, SELECT ON saved_tx_hashes TO check_sid_moscow_ingest;
GRANT USAGE ON SCHEMA public TO check_sid_moscow_ingest;
GRANT CONNECT ON DATABASE moscow_real_vote_db TO check_sid_moscow_ingest;

*/

async fn query_hash_of_saved_tx(
    client: std::sync::Arc<tokio_postgres::Client>,
) -> Result<std::collections::HashSet<voting_row::HashedTxRow>, Error> {
    let rows = client
        .query("SELECT TxHash, RowHash FROM saved_tx_hashes", &[])
        .await?;

    let mut hash_set = std::collections::HashSet::new();

    for row in rows {
        let tx_hash: String = row.try_get::<_, String>("TxHash")?;
        let row_hash: String = row.try_get::<_, String>("RowHash")?;
        hash_set.insert(voting_row::HashedTxRow { tx_hash, row_hash });
    }

    Ok(hash_set)
}

async fn insert_hash_of_saved_txs(
    client: std::sync::Arc<tokio_postgres::Client>,
    tx_data_batch: &[Box<dyn voting_row::VotingRow>],
) -> Result<(), Error> {
    let stmt = "
        INSERT INTO saved_tx_hashes (TxHash, RowHash)
        VALUES
    ";

    let mut values_clause = Vec::new();
    let mut params: Vec<&(dyn tokio_postgres::types::ToSql + Sync)> = Vec::new();

    let mut hashes: Vec<voting_row::HashedTxRow> = Vec::new();
    let n_elements = 2;
    for (index, tx_data) in tx_data_batch.iter().enumerate() {
        let i = index * n_elements + 1;
        let placeholders = (i..=i + n_elements - 1)
            .map(|n| format!("${}", n))
            .collect::<Vec<_>>()
            .join(", ");

        let placeholders = format!("({})", placeholders);
        values_clause.push(placeholders);

        hashes.push(tx_data.compute_hash());
    }

    for index in 0..tx_data_batch.len() {
        let hash_element = hashes.get(index).unwrap();

        params.extend_from_slice(&[&hash_element.tx_hash, &hash_element.row_hash]);
    }

    let values_str = values_clause.join(", ");
    let stmt = format!("{}{} ON CONFLICT DO NOTHING", stmt, values_str);
    client.execute(&stmt, &params[..]).await?;

    Ok(())
}

/*

CREATE TABLE moscow_blockchain_txs (
    Hash TEXT NOT NULL,
    FolderId TEXT NOT NULL,
    CreateVoting jsonb,
    StorageBallot jsonb,
    RegisterVoters jsonb,
    IssueBallot jsonb,
    StoragePrivateKey jsonb,
    StorageHistory jsonb,
    StorageResult jsonb,
    StorageDecodeBallot jsonb,
    StorageObserve jsonb,
    StorageBallotConfig jsonb,
    Type TEXT,
    Timestamp BIGINT,
    Sid TEXT,
    Io TEXT,
    VotingId TEXT,
    PRIMARY KEY (Hash, FolderId)
);

GRANT INSERT, SELECT, UPDATE, DELETE ON moscow_blockchain_txs TO check_sid_moscow_ingest;
GRANT USAGE ON SCHEMA public TO check_sid_moscow_ingest;
GRANT CONNECT ON DATABASE moscow_real_vote_db TO check_sid_moscow_ingest;

*/

#[async_recursion::async_recursion]
async fn insert_voting_data(
    client: std::sync::Arc<tokio_postgres::Client>,
    tx_data_batch: &[Box<dyn voting_row::VotingRow>],
    folder_id: &str,
) -> Result<(), Error> {
    let stmt = "
        INSERT INTO moscow_blockchain_txs (
            CreateVoting, StorageBallot, RegisterVoters, IssueBallot,
            StoragePrivateKey, StorageHistory, StorageResult,
            StorageDecodeBallot, StorageObserve, StorageBallotConfig,
            Type, Timestamp, Sid, Io, VotingId, Hash, FolderId
        )
        VALUES
    ";

    let mut datas = Vec::new();
    for tx_data in tx_data_batch.iter() {
        datas.push(tx_data.to_data());
    }

    let mut values_clause = Vec::new();

    let mut params: Vec<&(dyn tokio_postgres::types::ToSql + Sync)> = Vec::new();

    let n_elements = 17;
    for (index, data) in datas.iter().enumerate() {
        let i = index * n_elements + 1;
        let placeholders = (i..=i + n_elements - 1)
            .map(|n| format!("${}", n))
            .collect::<Vec<_>>()
            .join(", ");

        let placeholders = format!("({})", placeholders);
        values_clause.push(placeholders);

        params.extend_from_slice(&[
            &data.create_voting,
            &data.storage_ballot,
            &data.register_voters,
            &data.issue_ballot,
            &data.storage_private_key,
            &data.storage_history,
            &data.storage_result,
            &data.storage_decode_ballot,
            &data.storage_observe,
            &data.storage_ballot_config,
            &data.tx_type,
            &data.timestamp,
            &data.sid,
            &data.io,
            &data.voting_id,
            &data.hash,
            &folder_id,
        ]);
    }

    let values_str = values_clause.join(", ");
    let stmt = format!("{}{} ON CONFLICT DO NOTHING", stmt, values_str);

    match client.execute(&stmt, &params[..]).await {
        Ok(_) => {
            log::info!("Got successful send of chunk size {}", tx_data_batch.len());
        }
        Err(e) => {
            let e_str = e.to_string();
            log::info!("Got error {}", e_str);
            if e_str.contains("invalid message length: parameters is not drained")
                || e_str.contains("value too large to transmit")
            {
                if tx_data_batch.len() <= 100 {
                    log::error!(
                        "Cannot split the tx data batch further, got error anyway: {}",
                        e
                    );
                    return Err(e);
                }
                log::warn!(
                    "Got too large data to send to DB. TX data size is {} trying to send in two equal sized chunks",
                    tx_data_batch.len(),
                );
                insert_voting_data(
                    client.clone(),
                    &tx_data_batch[..tx_data_batch.len() / 2],
                    folder_id,
                )
                .await?;
                insert_voting_data(
                    client.clone(),
                    &tx_data_batch[tx_data_batch.len() / 2..],
                    folder_id,
                )
                .await?;
                return Ok(());
            }
            log::error!("error inserting data: {}", e);
            return Err(e);
        }
    }

    Ok(())
}

async fn write_batch(
    worker_id: usize,
    parsed_jsons: &[Box<dyn voting_row::VotingRow>],
    worker_client: std::sync::Arc<tokio_postgres::Client>,
    worker_directory_path: &str,
) {
    log::info!(
        "Worker #{}: Inserting {} rows",
        worker_id,
        parsed_jsons.len()
    );
    let timing = std::time::Instant::now();
    if let Err(error) =
        insert_voting_data(worker_client.clone(), parsed_jsons, worker_directory_path).await
    {
        log::error!(
            "Worker #{}: Failed to write value to DB: {}",
            worker_id,
            error
        )
    }
    log::info!(
        "Worker #{}: Inserting took {:?}",
        worker_id,
        timing.elapsed()
    );
    let timing = std::time::Instant::now();
    if let Err(error) = insert_hash_of_saved_txs(worker_client.clone(), parsed_jsons).await {
        log::error!(
            "Worker #{}: Failed to write value to DB: {}",
            worker_id,
            error
        )
    }
    log::info!(
        "Worker #{}: Writing TX hashes took {:?}",
        worker_id,
        timing.elapsed()
    );
}

const PG_BATCH_SIZE: usize = 1250;
const NUM_PG_WORKERS: usize = 2; // Number of concurrent workers

#[derive(Debug, PartialEq, clap::ValueEnum, Clone)]
enum ParsingMode {
    Voting2024,
    Voting2023,
}

#[derive(clap::Parser, Debug)]
#[clap(author, version, about, long_about = None)]
struct Args {
    /// Path to the directory with JSON files
    #[clap(value_parser)]
    directory_path: String,

    /// Parsing mode
    #[clap(value_enum, short, long, default_value_t = ParsingMode::Voting2024)]
    parsing_mode: ParsingMode,
}

fn parse_json_string(
    json_data: &str,
    parsing_mode: &ParsingMode,
) -> Option<Box<dyn voting_row::VotingRow>> {
    match parsing_mode {
        ParsingMode::Voting2024 => voting_row_2024::parse_json_string(json_data),
        ParsingMode::Voting2023 => {
            let voting_data: VotingData2023 = serde_json::from_str(json_data).ok()?;
            Some(Box::new(voting_data))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();

    let args = Args::parse();
    let directory_path = args.directory_path;
    let parsing_mode = args.parsing_mode;

    let pattern = format!("{}/*.json", directory_path);
    let glob_result: Vec<_> = glob::glob(&pattern)?.collect();

    if glob_result.is_empty() {
        log::error!("No files found in {}", directory_path);
        return Err("No files found".into());
    }

    log::info!("Found {} files to parse", glob_result.len());

    let cert = native_tls::Certificate::from_pem(&std::fs::read("certificate.pem")?)?;

    let connector = TlsConnector::builder().add_root_certificate(cert).build()?;
    let connector = MakeTlsConnector::new(connector);

    let conn_string = env::var("DATABASE_URL").expect("DATABASE_URL must be set");

    // Connect to PostgreSQL using the connection string from the environment variable
    let (client, connection) = tokio_postgres::connect(&conn_string, connector).await?;
    let client = std::sync::Arc::new(client);

    tokio::spawn(async move {
        if let Err(e) = connection.await {
            eprintln!("connection error: {}", e);
        }
    });

    log::info!("Querying saved txes hashes");
    let already_saved_txes = query_hash_of_saved_tx(client.clone()).await?;
    log::info!(
        "Already saved {} txes, I'm going to skip them",
        already_saved_txes.len()
    );

    // Set up channel for sending raw JSON strings from one task to another
    let (tx, rx) = async_channel::bounded(1000000);

    // Spawn a task for reading JSON lines
    tokio::spawn(async move {
        let mut n_lines_read = 0;
        let mut new_txes = 0;
        for (file_n, path) in glob_result.iter().enumerate() {
            match path {
                Ok(path) => {
                    log::info!("Reading file #{}: {:?}", file_n, path);
                    let err_msg = format!("cannot open file {:?}", &path);
                    let file = File::open(path).await.expect(&err_msg);

                    let reader = BufReader::new(file);
                    let mut lines = reader.lines();

                    while let Some(line) = lines.next_line().await.expect("Failed to read file") {
                        if n_lines_read % 10000 == 0 {
                            log::info!("Reading line {}", n_lines_read);
                        }
                        if let Some(parsed_json) = parse_json_string(&line) {
                            let hashed_tx_row = parsed_json.compute_hash();
                            let is_already_saved = already_saved_txes.contains(&hashed_tx_row);
                            if !is_already_saved {
                                if new_txes % 1000 == 0 {
                                    log::info!("Sending new tx #{}", new_txes);
                                }
                                let tx = tx.clone();
                                tx.send(parsed_json)
                                    .await
                                    .expect("failed to send json data");
                                new_txes += 1;
                            }
                        }
                        n_lines_read += 1;
                    }
                }
                Err(e) => eprintln!("error reading path: {}", e),
            }
        }
    });

    // Create multiple consumer tasks
    let mut tasks = Vec::new();

    for worker_id in 0..NUM_PG_WORKERS {
        let worker_rx = rx.clone();
        let worker_directory_path = directory_path.clone();
        let worker_client = client.clone();
        // Spawn a task for inserting data into the database
        let task = tokio::spawn(async move {
            log::info!("Starting Postgres ingest worker #{}", worker_id);
            let mut parsed_jsons: Vec<Box<dyn voting_row::VotingRow>> = Vec::new();
            while let Ok(parsed_json) = worker_rx.recv().await {
                parsed_jsons.push(parsed_json);
                if parsed_jsons.len() >= PG_BATCH_SIZE {
                    write_batch(
                        worker_id,
                        &parsed_jsons,
                        worker_client.clone(),
                        &worker_directory_path,
                    )
                    .await;
                    parsed_jsons = Vec::new();
                }
            }

            if !parsed_jsons.is_empty() {
                log::info!(
                    "Worker #{}: Last insert: inserting {} rows",
                    worker_id,
                    parsed_jsons.len()
                );
                write_batch(
                    worker_id,
                    &parsed_jsons,
                    worker_client.clone(),
                    &worker_directory_path,
                )
                .await;
            }
        });
        tasks.push(task);
    }

    // Remember to drop the original receiver to avoid a deadlock
    // as `async_channel` waits for all receivers to be dropped before closing
    drop(rx);

    // Await all tasks to complete
    for task in tasks {
        task.await?;
    }

    log::info!("Everyhing is done!");

    Ok(())
}
