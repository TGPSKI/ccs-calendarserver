----
-- Copyright (c) 2012-2016 Apple Inc. All rights reserved.
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
-- http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.
----

---------------------------------------------------
-- Upgrade database schema from VERSION 35 to 36 --
---------------------------------------------------

create table INBOX_CLEANUP_WORK (
    "WORK_ID" integer primary key not null,
    "NOT_BEFORE" timestamp default CURRENT_TIMESTAMP at time zone 'UTC'
);

create table CLEANUP_ONE_INBOX_WORK (
    "WORK_ID" integer primary key not null,
    "NOT_BEFORE" timestamp default CURRENT_TIMESTAMP at time zone 'UTC',
    "HOME_ID" integer not null unique references CALENDAR_HOME on delete cascade
);


-- update version
update CALENDARSERVER set VALUE = '36' where NAME = 'VERSION';


