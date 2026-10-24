-- Jet 4.0 DDL, run through ADO by scripts/build_mdb.ps1. Statements are split on ';'.
-- Lookup (parent) tables first, then the tables that reference them.

CREATE TABLE Agency (
    AgencyID      LONG CONSTRAINT pkAgency PRIMARY KEY,
    AgencyName    TEXT(100) NOT NULL,
    SubAgencyName TEXT(100) NOT NULL
);

CREATE TABLE Recipient (
    RecipientUEI  TEXT(12) CONSTRAINT pkRecipient PRIMARY KEY,
    RecipientName TEXT(100) NOT NULL
);

CREATE TABLE NAICS (
    NAICSCode        TEXT(6) CONSTRAINT pkNAICS PRIMARY KEY,
    NAICSDescription TEXT(255)
);

CREATE TABLE ActionType (
    ActionTypeCode        TEXT(2) CONSTRAINT pkActionType PRIMARY KEY,
    ActionTypeDescription TEXT(100) NOT NULL
);

CREATE TABLE Award (
    AwardKey     TEXT(80) CONSTRAINT pkAward PRIMARY KEY,
    PIID         TEXT(50) NOT NULL,
    AwardType    TEXT(30) NOT NULL,
    RecipientUEI TEXT(12) NOT NULL CONSTRAINT fkAwardRecipient REFERENCES Recipient (RecipientUEI),
    AgencyID     LONG NOT NULL CONSTRAINT fkAwardAgency REFERENCES Agency (AgencyID),
    NAICSCode    TEXT(6) CONSTRAINT fkAwardNAICS REFERENCES NAICS (NAICSCode),
    PSCCode      TEXT(4),
    Description  TEXT(255)
);

CREATE TABLE ContractAction (
    TransactionID  TEXT(100) CONSTRAINT pkContractAction PRIMARY KEY,
    AwardKey       TEXT(80) NOT NULL CONSTRAINT fkActionAward REFERENCES Award (AwardKey),
    ModNumber      TEXT(25) NOT NULL,
    ActionDate     DATETIME NOT NULL,
    ActionTypeCode TEXT(2) NOT NULL CONSTRAINT fkActionType REFERENCES ActionType (ActionTypeCode),
    Amount         CURRENCY NOT NULL
);

CREATE INDEX idxActionDate ON ContractAction (ActionDate);

-- Filled by the append query qappAgencyFYSummary; a snapshot table, the kind a monthly
-- report reads so last month's numbers do not move when late modifications arrive.
CREATE TABLE AgencyFYSummary (
    FiscalYear  INTEGER NOT NULL,
    AgencyID    LONG NOT NULL CONSTRAINT fkSummaryAgency REFERENCES Agency (AgencyID),
    ActionCount LONG NOT NULL,
    Obligated   CURRENCY NOT NULL,
    LoadedOn    DATETIME NOT NULL,
    CONSTRAINT pkAgencyFYSummary PRIMARY KEY (FiscalYear, AgencyID)
);
