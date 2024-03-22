use crate::capitalize_json::CapitalizeKeys;
use crate::voting_row;

use std::hash::{Hash, Hasher};

#[allow(non_snake_case)]
#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
struct VotingData {
    createVoting: Option<serde_json::Value>,
    storageBallot: Option<serde_json::Value>,
    registerVoters: Option<serde_json::Value>,
    issueBallot: Option<serde_json::Value>,
    storagePrivateKey: Option<serde_json::Value>,
    storageHistory: Option<serde_json::Value>,
    storageDecodeBallot: Option<serde_json::Value>,
    storageResult: Option<serde_json::Value>,
    storageObserve: Option<serde_json::Value>,
    storageBallotConfig: Option<serde_json::Value>,
}

#[allow(non_snake_case)]
#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct VotingTx {
    hash: String,
    timestamp: Option<i64>,
    #[serde(rename = "type")]
    tx_type: Option<String>,
    data: Option<String>, // not saved in Postgres, used to compute tx hash
    decodeData: Option<VotingData>,
    sid: Option<String>,
    io: Option<String>,
    votingId: Option<String>,
}

#[allow(non_snake_case)]
#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct TxData {
    txs: Vec<VotingTx>,
}

impl voting_row::VotingRow for VotingTx {
    fn to_data(&self) -> voting_row::VotingRowData {
        let voting_data_default = VotingData::default();
        let voting_data = self.decodeData.as_ref().unwrap_or(&voting_data_default);
        voting_row::VotingRowData {
            create_voting: voting_data.createVoting.capitalize_keys(),
            storage_ballot: voting_data.storageBallot.capitalize_keys(),
            register_voters: voting_data.registerVoters.capitalize_keys(),
            issue_ballot: voting_data.issueBallot.capitalize_keys(),
            storage_private_key: voting_data.storagePrivateKey.capitalize_keys(),
            storage_history: voting_data.storageHistory.capitalize_keys(),
            storage_decode_ballot: voting_data.storageDecodeBallot.capitalize_keys(),
            storage_result: voting_data.storageResult.capitalize_keys(),
            storage_observe: voting_data.storageObserve.capitalize_keys(),
            storage_ballot_config: voting_data.storageBallotConfig.capitalize_keys(),
            hash: self.hash.clone(),
            tx_type: self.tx_type.clone(),
            timestamp: self.timestamp,
            sid: self.sid.clone(),
            io: self.io.clone(),
            voting_id: self.votingId.clone(),
        }
    }
    fn compute_hash(&self) -> voting_row::HashedTxRow {
        let mut hasher = std::hash::DefaultHasher::new();
        let hash = match &self.data {
            Some(data) => {
                data.hash(&mut hasher);
                hasher.finish().to_string()
            }
            None => "None".into(),
        };
        voting_row::HashedTxRow {
            tx_hash: self.hash.clone(),
            row_hash: hash,
        }
    }
}

pub fn parse_json_string(json_data: &str) -> Option<Vec<Box<dyn voting_row::VotingRow>>> {
    let mut voting_rows: Vec<Box<dyn voting_row::VotingRow>> = Vec::new();
    match serde_json::from_str::<TxData>(json_data) {
        Ok(parsed_json) => {
            for tx in parsed_json.txs {
                if tx.decodeData.is_none() {
                    continue;
                }
                voting_rows.push(Box::new(tx));
            }
            Some(voting_rows)
        }
        Err(e) => {
            log::error!("error parsing json: {}", e);
            None
        }
    }
}
