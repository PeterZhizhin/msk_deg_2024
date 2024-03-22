use crate::voting_row;

use std::hash::{Hash, Hasher};

#[allow(non_snake_case)]
#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
struct VotingData {
    CreateVoting: Option<serde_json::Value>,
    StorageBallot: Option<serde_json::Value>,
    RegisterVoters: Option<serde_json::Value>,
    IssueBallot: Option<serde_json::Value>,
    StoragePrivateKey: Option<serde_json::Value>,
    StorageHistory: Option<serde_json::Value>,
    StorageDecodeBallot: Option<serde_json::Value>,
    StorageResult: Option<serde_json::Value>,
    StorageObserve: Option<serde_json::Value>,
    StorageBallotConfig: Option<serde_json::Value>,
}

#[allow(non_snake_case)]
#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct TxData {
    Hash: String,
    Type: Option<String>,
    Data: Option<String>, // not saved in Postgres, used to compute tx hash
    Timestamp: Option<i64>,
    DecodeData: Option<VotingData>,
    Sid: Option<String>,
    Io: Option<String>,
    VotingId: Option<String>,
}

impl voting_row::VotingRow for TxData {
    fn to_data(&self) -> voting_row::VotingRowData {
        let voting_data_default = VotingData::default();
        let voting_data = self.DecodeData.as_ref().unwrap_or(&voting_data_default);
        voting_row::VotingRowData {
            create_voting: voting_data.CreateVoting.clone(),
            storage_ballot: voting_data.StorageBallot.clone(),
            register_voters: voting_data.RegisterVoters.clone(),
            issue_ballot: voting_data.IssueBallot.clone(),
            storage_private_key: voting_data.StoragePrivateKey.clone(),
            storage_history: voting_data.StorageHistory.clone(),
            storage_decode_ballot: voting_data.StorageDecodeBallot.clone(),
            storage_result: voting_data.StorageResult.clone(),
            storage_observe: voting_data.StorageObserve.clone(),
            storage_ballot_config: voting_data.StorageBallotConfig.clone(),
            hash: self.Hash.clone(),
            tx_type: self.Type.clone(),
            timestamp: self.Timestamp,
            sid: self.Sid.clone(),
            io: self.Io.clone(),
            voting_id: self.VotingId.clone(),
        }
    }
    fn compute_hash(&self) -> voting_row::HashedTxRow {
        let mut hasher = std::hash::DefaultHasher::new();
        let hash = match &self.Data {
            Some(data) => {
                data.hash(&mut hasher);
                hasher.finish().to_string()
            }
            None => "None".into(),
        };
        voting_row::HashedTxRow {
            tx_hash: self.Hash.clone(),
            row_hash: hash,
        }
    }
}

pub fn parse_json_string(json_data: &str) -> Option<Box<dyn voting_row::VotingRow>> {
    match serde_json::from_str::<TxData>(json_data) {
        Ok(parsed_json) => {
            if parsed_json.DecodeData.is_none() {
                return None;
            }
            Some(Box::new(parsed_json))
        }
        Err(e) => {
            log::error!("error parsing json: {}", e);
            None
        }
    }
}
